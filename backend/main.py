"""FastAPI backend for chess game review."""

import json
import os
import time
from collections import deque
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

from backend.analysis_service import AnalysisService
from backend import auth as auth_mod
from backend.config import (
    AUTH_TOKEN_TTL_SECONDS,
    DEFAULT_DEPTH,
    MAX_DEPTH,
    get_auth_secret,
    get_gemini_api_key,
)
from backend import coach as coach_mod

_gemini_client = None
_coach_cache = {}
_move_comment_cache = {}


def _get_gemini():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    key = get_gemini_api_key()
    if not key:
        return None
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=key)
    except Exception:
        return None
    return _gemini_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        AnalysisService.get()
    except RuntimeError:
        pass
    yield
    try:
        AnalysisService.get().shutdown()
    except Exception:
        pass


app = FastAPI(title="Chess Game Review API", lifespan=lifespan)

_origins_env = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
_allow_origins = ["*"] if _origins_env.strip() == "*" else [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    pgn: str
    player_color: str = Field(default="White", pattern="^(White|Black)$")
    depth: int = Field(default=DEFAULT_DEPTH, ge=8, le=MAX_DEPTH)


class MoveReviewRequest(BaseModel):
    fen: str = Field(max_length=120)
    uci: str = Field(pattern="^[a-h][1-8][a-h][1-8][qrbn]?$")
    ply: int = Field(default=0, ge=0, le=600)
    history: list[str] | None = Field(default=None, max_length=600)
    depth: int = Field(default=DEFAULT_DEPTH, ge=8, le=MAX_DEPTH)


class AuthRequest(BaseModel):
    password: str = Field(max_length=512)


# --- Shared-secret gate -----------------------------------------------------
#
# The check lives on the server so it cannot be bypassed from the browser: dev
# tools, curl, or a forged frontend all hit the same require_auth dependency,
# which every compute/Gemini endpoint depends on. A missing token, a tampered
# or expired one, and an unset AUTH_SECRET are all refused before any Stockfish
# search or Gemini call runs.


def require_auth(authorization: str | None = Header(default=None)) -> None:
    secret = get_auth_secret()
    if not secret:
        # Fail closed: without a configured secret there is no safe way to let a
        # request through, so protect the API key rather than silently open up.
        raise HTTPException(status_code=503, detail="Authentication is not configured on the server.")
    token = authorization[7:].strip() if authorization and authorization[:7].lower() == "bearer " else ""
    if not auth_mod.verify_token(secret, token):
        raise HTTPException(status_code=401, detail="Authentication required or session expired.")


# Small in-memory throttle so the password can't be brute-forced online. Keyed
# by client IP; per-process only, which is fine for the single free-tier worker.
_AUTH_MAX_FAILURES = 8
_AUTH_WINDOW_SECONDS = 60.0
_auth_failures: dict[str, deque] = {}


def _auth_throttled(ip: str) -> bool:
    now = time.monotonic()
    hits = _auth_failures.get(ip)
    if hits is None:
        return False
    while hits and now - hits[0] > _AUTH_WINDOW_SECONDS:
        hits.popleft()
    return len(hits) >= _AUTH_MAX_FAILURES


def _record_auth_failure(ip: str) -> None:
    hits = _auth_failures.setdefault(ip, deque())
    hits.append(time.monotonic())


@app.post("/api/auth")
def authenticate(req: AuthRequest, request: Request):
    secret = get_auth_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Authentication is not configured on the server.")

    client_ip = request.client.host if request.client else "unknown"
    if _auth_throttled(client_ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Wait a minute and try again.")

    if not auth_mod.verify_password(secret, req.password):
        _record_auth_failure(client_ip)
        raise HTTPException(status_code=401, detail="Incorrect password.")

    _auth_failures.pop(client_ip, None)
    return {"token": auth_mod.issue_token(secret, AUTH_TOKEN_TTL_SECONDS), "expires_in": AUTH_TOKEN_TTL_SECONDS}


@app.get("/api/health")
def health():
    try:
        svc = AnalysisService.get()
        info = svc.health()
        info["gemini_configured"] = get_gemini_api_key() is not None
        info["default_depth"] = DEFAULT_DEPTH
        return info
    except RuntimeError as exc:
        return {"ready": False, "error": str(exc), "gemini_configured": get_gemini_api_key() is not None}


@app.get("/api/position", dependencies=[Depends(require_auth)])
def analyse_position(
    fen: str = Query(...),
    depth: int = Query(default=DEFAULT_DEPTH, ge=8, le=MAX_DEPTH),
    multipv: int = Query(default=3, ge=1, le=5),
):
    try:
        svc = AnalysisService.get()
        lines = svc.analyse_position(fen, depth=depth, multipv=multipv)
        return {"fen": fen, "depth": depth, "lines": lines}
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _sse_event(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/analyze", dependencies=[Depends(require_auth)])
def analyze_game(req: AnalyzeRequest):
    gemini = _get_gemini()
    if gemini is None:
        raise HTTPException(
            status_code=400,
            detail="GEMINI_API_KEY is required. Set it in .env or environment.",
        )

    def stream():
        try:
            svc = AnalysisService.get()
        except RuntimeError as exc:
            yield _sse_event("error", {"message": str(exc)})
            return

        complete = None
        try:
            for event_type, payload in svc.analyze_streaming(
                req.pgn, depth=req.depth, player_color=req.player_color
            ):
                if event_type == "cached":
                    complete = payload
                    yield _sse_event("progress", {"ply": payload["move_data"][-1]["ply"] + 1
                                                    if payload["move_data"] else 0,
                                                    "total": len(payload["move_data"]),
                                                    "cached": True})
                    break
                elif event_type == "progress":
                    yield _sse_event("progress", payload)
                elif event_type == "complete":
                    complete = payload

            if complete is None:
                yield _sse_event("error", {"message": "Analysis produced no result"})
                return

            summary, comments = coach_mod.generate_coach(
                complete["move_data"],
                req.player_color,
                gemini,
                complete.get("critical_moments"),
                _cache=_coach_cache,
            )

            result = {
                "move_data": complete["move_data"],
                "stats": complete["stats"],
                "meta": complete["meta"],
                "hist": complete["hist"],
                "critical_moments": complete["critical_moments"],
                "coach": {"summary": summary, "comments": comments},
                "player_color": req.player_color,
            }
            yield _sse_event("complete", result)
        except (ValueError, TimeoutError) as exc:
            yield _sse_event("error", {"message": str(exc)})
        except Exception as exc:
            yield _sse_event("error", {"message": f"Analysis failed: {exc}"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/move-review", dependencies=[Depends(require_auth)])
def move_review(req: MoveReviewRequest):
    """Review one move played from an arbitrary position (variation exploration).

    Unlike /api/analyze this does not require Gemini — generate_move_comment
    falls back to the fact-based template when the key is missing or the free
    tier rate-limits us, so board exploration keeps working either way.
    """
    try:
        svc = AnalysisService.get()
        move = svc.analyse_move(
            req.fen, req.uci, depth=req.depth, ply=req.ply, uci_history=req.history
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    comment = coach_mod.generate_move_comment(
        move, _get_gemini(), _cache=_move_comment_cache
    )
    return {"move": move, "comment": comment}


@app.get("/api/icons/{name}")
def icon(name: str):
    from fastapi.responses import FileResponse
    icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons")
    mapping = {
        "Brilliant": "Brilliant.png",
        "Great": "Great.png",
        "Best": "Best.png",
        "Excellent": "Excellent.png",
        "Good": "Good.png",
        "Book": "Book.png",
        "Inaccuracy": "Inaccuracy.PNG",
        "Miss": "Miss.png",
        "Mistake": "Mistake.png",
        "Blunder": "Blunder.png",
    }
    fname = mapping.get(name)
    if not fname:
        raise HTTPException(status_code=404)
    path = os.path.join(icons_dir, fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)

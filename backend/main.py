"""FastAPI backend for chess game review."""

import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

from backend.analysis_service import AnalysisService
from backend.config import DEFAULT_DEPTH, MAX_DEPTH, get_gemini_api_key
from backend import coach as coach_mod

_gemini_client = None
_coach_cache = {}


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    pgn: str
    player_color: str = Field(default="White", pattern="^(White|Black)$")
    depth: int = Field(default=DEFAULT_DEPTH, ge=8, le=MAX_DEPTH)


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


@app.get("/api/position")
def analyse_position(
    fen: str = Query(...),
    depth: int = Query(default=DEFAULT_DEPTH, ge=8, le=MAX_DEPTH),
    multipv: int = Query(default=3, ge=1, le=5),
):
    try:
        svc = AnalysisService.get()
        lines = svc.analyse_position(fen, depth=depth, multipv=multipv)
        return {"fen": fen, "depth": depth, "lines": lines}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _sse_event(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/analyze")
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
        except ValueError as exc:
            yield _sse_event("error", {"message": str(exc)})
        except Exception as exc:
            yield _sse_event("error", {"message": f"Analysis failed: {exc}"})

    return StreamingResponse(stream(), media_type="text/event-stream")


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
        "Inaccuracy": "Inacuracy.png",
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

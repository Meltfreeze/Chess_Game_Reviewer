# AI Chess Game Reviewer

A chess.com-style game review app: a FastAPI backend (Stockfish + Gemini) and a
React frontend.

## Architecture

```
backend/   FastAPI app. Stockfish is the only source of chess truth;
           Gemini only rephrases facts the engine has already verified.
frontend/  React + Vite + TypeScript SPA. Talks to the backend over HTTP/SSE.
icons/     Move-classification badge images, served by the backend.
```

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app: `/api/health`, `/api/position`, `/api/analyze` (SSE), `/api/icons/{name}` |
| `backend/engine.py` | All chess analysis: SEE/sacrifice detection, move classification, critical moments |
| `backend/coach.py` | Turns engine-verified facts into text (a single batched Gemini call per game) |
| `backend/analysis_service.py` | Singleton Stockfish process wrapper + in-memory analysis cache |
| `backend/config.py` | Resolves the Stockfish binary path and reads config from the environment |
| `backend/openings.py` | ECO opening-name lookup |
| `frontend/src/App.tsx` | Owns analysis state, wires the board/eval bar/eval graph/move list/coach panel together |
| `frontend/src/api/client.ts` | Typed fetch wrappers for the backend API, including SSE parsing |
| `frontend/src/components/` | Presentational board, move list, eval bar/graph, and coach panel |

### Why Gemini can't hallucinate
`backend/engine.py` computes every fact from `python-chess` + Stockfish first —
the engine's preferred move, what is *actually* hanging (verified with a static
exchange evaluation), whether the move was a capture/check/castle, and the
opponent's concrete refutation. Gemini receives only those verified facts and is
instructed to rephrase them, never invent new ones; `backend/coach.py` validates
the response only uses vocabulary drawn from those facts. Only "notable" moves
(blunders, mistakes, brilliancies, misses, etc.) are sent to Gemini, batched into
a single request per game, and cached — reopening a game costs zero calls.

## Local development

```bash
# Backend (terminal 1)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload   # http://127.0.0.1:8000

# Frontend (terminal 2)
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000` (see
`frontend/vite.config.ts`), so no extra frontend config is needed locally.

### Stockfish

The `stockfish` binary committed at the repo root via Git LFS is a **Linux**
build (for cloud/Docker deployment) — it will not run on macOS or Windows.
For local development, install Stockfish for your OS (e.g. `brew install
stockfish` on macOS) and set `STOCKFISH_PATH` in `.env` to its location.
`backend/config.py` resolution order: `STOCKFISH_PATH` env var → a binary
named `stockfish`/`stockfish-ubuntu-x86-64`/`stockfish-linux` (or the
`.exe` equivalents on Windows) at the repo root → `stockfish` on `PATH`.

To pull the real Linux binary from Git LFS: `git lfs install --local && git lfs pull`.

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | Yes, for coaching | Gemini API key used by `backend/coach.py` |
| `STOCKFISH_PATH` | No | Absolute path to a Stockfish binary, overrides auto-detection |
| `ANALYSIS_DEPTH` | No | Default engine search depth (default `18`) |
| `ALLOWED_ORIGINS` | No | Comma-separated list of origins the backend accepts CORS requests from (default `http://localhost:5173,http://127.0.0.1:5173`); use `*` to allow any origin |
| `VITE_API_BASE_URL` | No | Set in the frontend build/env to point at a deployed backend URL instead of the relative `/api` dev-proxy path |

## Deployment

- **Frontend**: deploy `frontend/` to Vercel (set the project root to
  `frontend/`; `frontend/vercel.json` handles the SPA rewrite). Set
  `VITE_API_BASE_URL` to the deployed backend's URL.
- **Backend**: containerize with `backend/Dockerfile` (build from the repo
  root: `docker build -f backend/Dockerfile -t chess-backend .`) and deploy
  to any container host. Set `GEMINI_API_KEY` and `ALLOWED_ORIGINS` (pointing
  back at the deployed frontend origin) as environment variables on that host.

## Possible next steps
- Opening moves are labeled "Book" via `backend/openings.py`'s small ECO
  lookup table — extend it for a fuller opening database.
- No automated tests yet.

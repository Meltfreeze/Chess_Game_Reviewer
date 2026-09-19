# AI Chess Game Reviewer

A full-stack chess review app inspired by game-review products on major chess
platforms. It analyzes a PGN with Stockfish, streams move-by-move results to a
React interface, and adds concise coaching comments grounded exclusively in
engine-verified facts.

## Features

- Streams full-game Stockfish analysis over Server-Sent Events (SSE).
- Classifies moves and calculates per-side accuracy and game summaries.
- Explains notable moves using verified tactical and positional facts.
- Uses Gemini optionally for prose; deterministic coaching remains available
  when Gemini is disabled or rejects an unsupported response.
- Supports click-to-move, drag-to-move, alternate-line exploration, and branch
  navigation on an interactive board.
- Keeps selections, legal-move indicators, captures, last-move highlights,
  coordinates, and input mapping correct when the board is flipped.
- Includes evaluation bars and graphs, move navigation, move-classification
  badges, and configurable analysis depth.
- Protects engine-heavy endpoints with a shared-secret, stateless token flow.

## How analysis works

```text
Browser
  -> authenticate with the configured shared secret
  -> submit a PGN to /api/analyze
  -> receive incremental SSE results
  -> render the board, move tree, evaluations, and coaching

Backend
  -> serialize Stockfish access through AnalysisService
  -> analyze each position with MultiPV=2
  -> classify moves and derive verified facts in engine.py
  -> turn those facts into prose in coach.py
  -> reject unsupported or unjustified LLM comments
  -> use a deterministic fact-based comment when validation fails
```

Stockfish and `python-chess` are the only sources of chess truth. Gemini does
not analyze positions independently: it receives facts already proved by the
engine, and its output is checked for unsupported pieces/squares and for a
concrete citation on notable moves. This includes engine continuations,
opponent replies, missed captures, hanging or pinned pieces, sacrifices, and
runner-up moves where relevant.

Analysis results and generated coaching are cached in memory. The app does not
currently use a database, so caches reset whenever the backend process restarts.

## Repository structure

```text
backend/                 FastAPI API, Stockfish analysis, and coaching
  main.py                Routes, validation, authentication, and SSE streaming
  engine.py              Evaluation, move classification, and verified facts
  coach.py               Gemini prompting, validation, and fallback comments
  analysis_service.py    Shared engine lifecycle, locking, and result cache
  auth.py                HMAC-signed shared-secret authentication tokens
  config.py              Environment settings and Stockfish discovery
  openings.py            ECO opening lookup
  data/openings.tsv      Opening data used by the lookup module
  tests/                  Backend unit and integration-style tests
  tools/build_openings.py Opening-data build utility
  Dockerfile             Production backend image

frontend/                React, TypeScript, Vite, and Tailwind SPA
  src/App.tsx             Top-level review and analysis state
  src/moveTree.ts         Main-line and alternate-variation navigation
  src/api/                Authentication and typed backend clients
  src/components/         Board, navigation, evaluation, moves, and coaching UI
  src/types.ts            Shared frontend response and move-fact types
  public/pieces/          Chess-piece images served by Vite/Vercel
  vercel.json             SPA routing configuration

icons/                   Move-classification badges served by the backend
pieces/                  Source copy of the chess-piece artwork
```

## Local development

### Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer and npm
- A Stockfish executable compatible with your operating system
- Git LFS if you need the repository's Linux Stockfish binary

### 1. Configure the backend

Create `.env` in the repository root:

```dotenv
AUTH_SECRET=choose-a-strong-shared-password
STOCKFISH_PATH=C:\path\to\stockfish.exe

# Optional: enables Gemini-written comments after fact validation.
GEMINI_API_KEY=
```

`AUTH_SECRET` is required. Protected endpoints fail closed when it is missing.
`STOCKFISH_PATH` can be omitted if a supported binary exists at the repository
root or `stockfish` is available on `PATH`.

Create the environment and install dependencies:

```powershell
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python -m uvicorn backend.main:app --reload
```

```bash
# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m uvicorn backend.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

### 2. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to
`http://127.0.0.1:8000`, so `VITE_API_BASE_URL` is not needed locally.

### Stockfish discovery

`backend/config.py` resolves Stockfish in this order:

1. A valid `STOCKFISH_PATH`.
2. A platform-appropriate binary at the repository root.
3. `stockfish` on `PATH`.

The Git LFS binary at the repository root is for Linux deployment and will not
run natively on Windows or macOS. To retrieve it:

```bash
git lfs install --local
git lfs pull
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `AUTH_SECRET` | none | Required shared password used to issue signed access tokens. |
| `AUTH_TOKEN_TTL_SECONDS` | `43200` | Authentication token lifetime in seconds. |
| `STOCKFISH_PATH` | auto-detected | Absolute path to a Stockfish executable. |
| `ANALYSIS_DEPTH` | `16` | Default search depth; API requests accept depths from 8 through 22. |
| `ENGINE_TIME_LIMIT_SECONDS` | `10` | Per-search Stockfish time ceiling. |
| `ENGINE_LOCK_TIMEOUT_SECONDS` | `45` | Maximum wait for the shared engine lock. |
| `GEMINI_API_KEY` | none | Enables optional Gemini phrasing of verified coaching facts. |
| `ALLOWED_ORIGINS` | local Vite origins | Comma-separated CORS origins; `*` allows any origin. |
| `VITE_API_BASE_URL` | relative `/api` | Backend origin used by a deployed frontend build. |
| `PORT` | `8000` | Port used by the backend container command. |

Keep backend secrets in the backend deployment environment. Do not expose
`AUTH_SECRET` or `GEMINI_API_KEY` through `VITE_` variables.

## API

| Method | Route | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth` | Public | Exchange the shared password for a short-lived bearer token. |
| `GET` | `/api/health` | Public | Report API and engine availability. |
| `GET` | `/api/icons/{name}` | Public | Serve a move-classification badge. |
| `GET` | `/api/position` | Bearer | Return a validated position and legal moves for a move history. |
| `POST` | `/api/analyze` | Bearer | Stream a complete PGN review as SSE events. |
| `POST` | `/api/move-review` | Bearer | Analyze one explored move or variation. |

Authentication is deliberately lightweight: the password is compared on the
backend, and successful login returns an expiring HMAC-signed token kept in the
browser session. It is suitable for controlling access to a private deployment,
not as a multi-user account or authorization system.

## Testing and verification

Run the backend suite from the repository root:

```powershell
.venv\Scripts\python.exe -m pytest
```

Run frontend tests and the production typecheck/build:

```bash
cd frontend
npm test
npm run build
```

The backend tests cover authentication, move classification, openings,
verified engine facts, coaching validation, deterministic fallbacks, and SSE
serialization. Frontend tests cover the analysis form and core review controls.

## Deployment

### Backend on Render

Deploy from the repository root using `backend/Dockerfile`. The image installs
Stockfish, copies the backend and classification icons, and starts Uvicorn on
`PORT`.

Configure at least:

- `AUTH_SECRET`
- `ALLOWED_ORIGINS` with the deployed frontend origin
- `GEMINI_API_KEY` if Gemini-authored coaching is desired

The backend holds one shared engine process and an in-memory cache. Render cold
starts restart both, and horizontal instances do not share cached results.

### Frontend on Vercel

Create a Vercel project with `frontend/` as its root directory, then set:

```dotenv
VITE_API_BASE_URL=https://your-backend.example.com
```

`frontend/vercel.json` rewrites application routes to `index.html` for SPA
navigation. Add the final Vercel origin to the backend's `ALLOWED_ORIGINS`.

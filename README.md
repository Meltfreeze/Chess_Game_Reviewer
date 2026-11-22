# AI Chess Game Reviewer

A full-stack chess review app inspired by game-review products on major chess
platforms. It analyzes a PGN with server-side Stockfish, streams analysis progress
to a React interface, and adds coaching based on facts derived from the engine
and `python-chess`. Optional Gemini prose is checked by heuristic validators
and replaced with deterministic comments when rejected.

Implementation checked on 2026-11-22. For coding-agent instructions and a source
map, read [AGENTS.md](AGENTS.md). [CLAUDE.md](CLAUDE.md) references that same guide.
Source code and tests take precedence if documentation has drifted.

## Features

- Streams full-game Stockfish analysis over Server-Sent Events (SSE).
- Previews pasted, uploaded, or dropped PGN locally, including players, result,
  final position, and opening recognition. The form rejects empty/invalid games,
  detected multiple games, and explicitly non-standard variants.
- Classifies moves and calculates per-side accuracy and game summaries.
- Explains notable moves using verified tactical and positional facts.
- Uses Gemini optionally for prose; deterministic coaching remains available
  when Gemini is disabled, generation fails, or validation rejects its response.
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
  -> receive SSE progress counts while the engine works
  -> wait for the complete payload, including coaching
  -> render the board, move tree, evaluations, and coaching

Backend
  -> serialize Stockfish access through AnalysisService
  -> search positions with MultiPV=2 at fast or deep limits
  -> deepen uncertain and likely Great/Brilliant moves
  -> classify moves and derive verified facts in engine.py
  -> turn those facts into prose in coach.py
  -> validate LLM comments and the game summary
  -> use a deterministic fact-based comment when validation fails
```

Stockfish and `python-chess` supply evaluations, legal moves, and tactical facts;
application heuristics derive classifications and scoring. Gemini receives those
facts rather than analyzing positions independently. Its comments are checked for
unsupported pieces/squares, forbidden move numbers, and for a
concrete citation on notable moves. This includes engine continuations,
opponent replies, missed captures, hanging or pinned pieces, sacrifices, and
runner-up moves where relevant.

For a notable capture whose landing piece has a legal, locally profitable
recapture, the engine adds an optional `facts.capture_consequence`: the exact
recapture, a short Stockfish line, immediate material change from the exchange,
and the mover-relative evaluation after that line. Coaching must reconcile this
fact instead of merely calling the piece "hanging". Attacks that cannot make a
legal profitable capture, including attacks by a pinned piece, are not reported
as recaptures.

These checks reduce unsupported prose; they are not a semantic proof of every
claim. Both sides are reviewed equally; there is no player-color setting.

The browser uses POST `fetch` with a stream reader, not `EventSource`. It consumes
progress counts but does not render streamed move entries as they arrive. After
engine analysis, coaching finishes before the final `complete` event. There is no
background job queue, persistence, stream heartbeat, or resume protocol.

### Search and scoring

[backend/engine.py](backend/engine.py) implements adaptive MultiPV=2 review for
both full games and explored moves. The fast pass normally searches at depth 10;
selected tactical, uncertain, and Great/Brilliant candidates deepen to the
requested depth. A sacrifice may require an additional search restricted to
captures of the offered piece. Requests at or below the fast depth use one set
of search limits. Each search has a time ceiling; requested depth is not a
guarantee that every search reaches that depth.

Adjacent moves reuse position analysis. A move is held until the next move has
been inspected because its destination may need a deeper search as the next
starting position. Progress counts completed plies, not full move pairs.

Classification precedence is checkmate (`Best`), `Book`, negative evaluation
labels, `Miss`, `Brilliant`, `Great`, then the remaining positive labels. Book
requires an opening-sequence prefix within 12 plies and a post-move evaluation
within 80 centipawns of equality (strictly less than 80 in absolute value).
Opening naming uses the longest named prefix and can extend beyond the Book cap.

Great requires the exact engine-best move and a meaningful gap to the runner-up,
with obvious moves excluded. Brilliant requires the exact best move, verified
non-pawn material investment, and its own eligibility checks; it does not require
the Great runner-up-gap test. These are project-specific
heuristics, not a claim of parity with chess.com's implementation.

Accuracy uses an exponential move score from lost win expectancy, aggregated
using a volatility-weighted mean and harmonic mean. The displayed estimated
performance is a heuristic derived from average centipawn loss, not a measured
player rating. The classification probability curve and accuracy curve differ.

### Coaching and completion status

[backend/coach.py](backend/coach.py) currently defaults to the hard-coded model
ID `gemini-3.5-flash-lite`. There is no environment setting for the model. A game
requests one summary plus comments for at most 24 notable moves, prioritizing
centipawn loss when needed. Other moves retain deterministic comments. A single
variation move has a separate comment-generation path.

The response distinguishes engine completion from Gemini generation and validation:

- `commentary_succeeded`: the generated summary and every requested comment
  passed validation. Non-requested move comments can still be templates.
- `all_comments_succeeded`: compatibility alias of `commentary_succeeded`.
- `commentary_status`: attempted/complete generation, generated/accepted summary,
  requested/generated/accepted comment counts, and whether fallback was used.

The preview card's `Status: Success` uses `gemini_attempted && generation_complete`;
otherwise a completed engine review is labeled `Review complete — coaching fallback used`
when detailed status exists, even if validation rejected some prose. With older
responses it falls back to the success boolean. The completion label therefore
describes the Stockfish result independently from whether Gemini output was available.

### Caching and concurrency

[AnalysisService](backend/analysis_service.py) holds one lazily started Stockfish
process per Python process. A timed lock serializes game, position, and move
searches. A waiting game request rechecks the cache after acquiring the lock.

| Cache | Key inputs | Scope |
| --- | --- | --- |
| Engine game result | Trimmed PGN text, depth, fast depth/time, search time, threads, hash size | Complete engine result, before coaching |
| Game coaching | UCI move sequence and classifications | Summary, comments, and status, including fallbacks |
| Move coaching | Starting FEN, played UCI, classification | One comment, including fallback |

All three are unbounded in-memory dictionaries with no TTL or eviction. They
reset on restart and are not shared across workers/instances. Semantically
identical PGNs with different text can miss the game cache. Coaching keys omit
model, depth, and full facts, so they do not guarantee freshness when those change.
Position and single-move engine results have no application-level cache; the
Stockfish hash table is separate. There is no database or saved-review service.

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
  src/pgnPreview.ts       Local PGN validation and final-position preview
  src/openingLookup.ts    Browser lookup of the longest named opening prefix
  src/api/                Authentication and typed backend clients
  src/components/         Board, navigation, evaluation, moves, and coaching UI
  src/types.ts            Shared frontend response and move-fact types
  public/pieces/          Chess-piece images served by Vite/Vercel
  public/data/openings.tsv Browser copy of opening data (sync explicitly)
  vercel.json             SPA routing configuration

icons/                   Move-classification badges served by the backend
pieces/                  Source copy of the chess-piece artwork
```

## Local development

### Prerequisites

- Python 3.11 or newer
- Node.js and npm compatible with the locked Vite 5/Vitest 2 toolchain
  (their declared Node engine ranges include 18 and 20+; use a supported runtime)
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
`STOCKFISH_PATH` can be omitted if a compatible binary is found at the repository
root or on `PATH`. `backend/main.py` loads `.env` before importing settings;
running low-level modules directly does not itself load `.env`.

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
npm ci
npm run dev
```

Open `http://localhost:3000`. Vite proxies `/api` to
`http://127.0.0.1:8000`, so `VITE_API_BASE_URL` is not needed locally.

### Stockfish discovery

`backend/config.py` resolves Stockfish in this order:

1. An existing path from `STOCKFISH_PATH`.
2. On Windows: `stockfishw.exe`, `stockfish.exe`, then
   `stockfish-windows-x86-64.exe` at the repository root. On other platforms:
   `stockfish`, `stockfish-ubuntu-x86-64`, then `stockfish-linux`.
3. `stockfish` on `PATH`.

Discovery checks existence, not architecture or UCI compatibility. Set an explicit
path to your platform's executable, especially on macOS where the root Linux
file would otherwise be chosen before a `PATH` installation. The Git LFS binary
at the repository root is for Linux deployment. To retrieve it when needed:

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
| `FAST_ANALYSIS_DEPTH` | `10` | Depth of the first MultiPV=2 pass; requests at or below this depth use a single pass. |
| `FAST_ANALYSIS_TIME_SECONDS` | `1.5` | Time ceiling for each fast-pass search. |
| `ENGINE_THREADS` | `1` | Stockfish CPU threads; raise only if the backend has spare cores. |
| `ENGINE_HASH_MB` | `32` | Stockfish hash memory in MB; raise only if the backend has spare RAM. |
| `ENGINE_LOCK_TIMEOUT_SECONDS` | `45` | Maximum wait for the shared engine lock. |
| `GEMINI_API_KEY` | none | Enables optional Gemini phrasing of verified coaching facts. |
| `ALLOWED_ORIGINS` | local Vite origins | Comma-separated CORS origins; `*` allows any origin. |
| `VITE_API_BASE_URL` | empty string | Build-time backend origin; client appends `/api/...`. Empty means same-origin requests. Do not include `/api` in the value. |
| `PORT` | `8000` | Port used by the backend container command. |

Keep backend secrets in the backend deployment environment. Do not expose
`AUTH_SECRET` or `GEMINI_API_KEY` through `VITE_` variables.

The frontend slider and client helpers independently default to depth 16;
`ANALYSIS_DEPTH` only controls the backend default. Configuration constants are
read at import, so restart the backend after changing them. There is no
whole-game timeout setting: the engine limits apply per search and lock wait.

## API

| Method | Route | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth` | Public | Exchange the shared password for a short-lived bearer token. |
| `GET` | `/api/health` | Public | Report API and engine availability. |
| `GET` | `/api/icons/{name}` | Public | Serve a move-classification badge. |
| `GET` | `/api/position` | Bearer | Analyze a FEN and return engine principal variations. |
| `POST` | `/api/analyze` | Bearer | Stream a complete PGN review as SSE events. |
| `POST` | `/api/move-review` | Bearer | Analyze one explored move or variation. |

Authentication is deliberately lightweight: the password is compared on the
backend, and successful login returns an expiring HMAC-signed token kept in the
browser session. It is suitable for controlling access to a private deployment,
not as a multi-user account or authorization system. Tokens use an expiry payload
and HMAC-SHA256 signature, not JWT. The frontend stores them under `cgr_auth` in
`sessionStorage` (with an in-memory fallback) and treats them as expired 30 seconds
early. Full-game analysis is replayed after reauthentication.

### Request and stream contracts

- `/api/auth`: JSON `{ "password": "..." }` (maximum 512 characters); returns
  `token` and `expires_in`. Missing server secret yields 503; wrong password 401.
  After eight failures within 60 seconds per client IP, further attempts receive
  429 until the rolling window clears. The throttle is per process.
- `/api/position`: required `fen` query, optional `depth` (8–22) and `multipv`
  (1–5, default 3). Returns `{ fen, depth, lines }`; each line has `eval`,
  `eval_cp_white`, `first_uci`, and `san_line`. This endpoint is not currently
  called by the frontend. Runtime/lock failures return 503; other exceptions,
  including invalid-FEN parsing errors, currently return 500.
- `/api/analyze`: JSON `{ "pgn": "...", "depth": 16 }`. SSE event types are
  `progress`, `complete`, and `error`. Normal progress contains `ply`, `total`,
  and `move`; a cache hit emits one progress event with `cached: true` and no
  move. `complete` includes `move_data`, `stats`, `meta`, `hist`,
  `critical_moments`, `coach`, and the commentary status fields above. `error`
  contains `message`; after streaming starts, failures are events rather than
  non-2xx HTTP responses.
- `/api/move-review`: JSON with `fen` (at most 120 characters), legal UCI `uci`
  (optional promotion suffix `q/r/b/n`), optional `ply` (0–600, default 0),
  `history` (up to 600 UCI strings), and `depth` (8–22). History is the path
  from the standard start up to, excluding, the reviewed move. Omit it when
  unknown. Returns `{ move, comment }`. Invalid moves/FENs raise 400; unavailable
  or busy engine raises 503. Request-schema violations yield 422.
- `/api/health`: public engine startup/readiness probe. When available it includes
  `engine_path`, `version`, `default_depth`, and `gemini_configured`. HTTP 200
  alone does not mean ready: inspect `ready` and `error`. `gemini_configured`
  checks environment presence, not successful Gemini access.
- `/api/icons/{name}`: fixed classification-name mapping; unknown or missing
  files return 404. Case matters, including the file `Inaccuracy.PNG`.

Protected routes require `Authorization: Bearer <token>`; missing, invalid, or
expired tokens yield 401 and an unconfigured `AUTH_SECRET` yields 503. The
backend route definitions are in [backend/main.py](backend/main.py); frontend
consumer types are maintained manually in [types.ts](frontend/src/types.ts).

Move evaluations are White-relative centipawns at `eval_cp_white`; fact
evaluations are mover-relative pawns. Move and critical-moment `ply` values are
zero-based, while progress is a one-based count and tree positions start at root
0. `fen_before` precedes the move and `fen` follows it. Top-level `best_move` is
UCI, not SAN. See [AGENTS.md](AGENTS.md) for further contract invariants.

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

On macOS/Linux, use `.venv/bin/python -m pytest`. Backend tests cover
authentication, classification, openings, adaptive search/facts with engine
doubles, caching/locking, coaching validation/fallbacks, SSE serialization, and
Dockerfile configuration assertions. Frontend tests cover preview parsing and
opening lookup, form states, duplicate-analysis prevention, commentary status,
and board/navigation/evaluation orientation.

The production build runs TypeScript checking followed by Vite. No lint script,
backend type-checker, or browser end-to-end suite is configured. Tests do not
verify real Stockfish output, Gemini credentials/model availability, a Docker
image build, or live deployment. Run `git diff --check` before handing off edits.

## Opening data and artwork

Opening lookup uses the generated Lichess opening dataset recorded in the TSV
headers. It matches UCI sequence prefixes, not equivalent FEN positions reached
by transposition. The backend loads its table at import and fails if it is
missing; browser preview loads its separate static copy and tolerates lookup
failure without invalidating the PGN. Both copies currently contain the same
3,810 parsed entries.

To intentionally refresh the dataset from the generator's configured upstream:

```powershell
python backend/tools/build_openings.py
Copy-Item -LiteralPath backend/data/openings.tsv -Destination frontend/public/data/openings.tsv
```

On macOS/Linux, use `cp backend/data/openings.tsv frontend/public/data/openings.tsv`
for the second command. The generator also accepts `--src DIR` for local
`a.tsv`–`e.tsv` inputs and `--out PATH`. It only writes the backend copy by
default. Inspect the diff and rerun opening/preview tests after a refresh.

Runtime piece art is in `frontend/public/pieces/`; root `pieces/` is a separate
copy. Classification badges come from backend `icons/` via the fixed API mapping.

## Deployment

### Backend on Render

Build with repository-root context and `backend/Dockerfile`. The image downloads
the repository's Linux Stockfish 19 binary from Git LFS, verifies its pinned
SHA-256 checksum and UCI version, copies the backend and classification icons,
and starts Uvicorn on `PORT`. It uses Python 3.11 and installs only
`requirements.txt`. Docker build arguments `STOCKFISH_URL` and `STOCKFISH_SHA256`
control the binary download and checksum; the Dockerfile also checks the UCI
name is exactly `Stockfish 19`.

Configure at least:

- `AUTH_SECRET`
- `ALLOWED_ORIGINS` with the deployed frontend origin
- `GEMINI_API_KEY` if Gemini-authored coaching is desired

The container command starts one Uvicorn worker. Process restarts discard caches
and require the engine to start again. Additional workers/instances each consume
their own engine resources and do not share cached results or auth throttles.
The repository does not encode the live Render tier, CPU/RAM allocation, sleep
policy, or proxy timeouts; verify these in the deployment before changing capacity.

The default download URL points at the remote repository's `main/stockfish`, not
the binary from the local Docker build context. A binary update must coordinate
that URL/ref, checksum, and UCI-name check. An incompatible executable, checksum
failure, or name mismatch fails the build. A ready deployment should report
`/usr/local/bin/stockfish` and `Stockfish 19` from `/api/health`.

### Frontend on Vercel

Create a Vercel project with `frontend/` as its root directory, then set:

```dotenv
VITE_API_BASE_URL=https://your-backend.example.com
```

`frontend/vercel.json` rewrites application routes to `index.html` for SPA
navigation. Add the final Vercel origin to the backend's `ALLOWED_ORIGINS`.
The configured origin is embedded at build time, so changing it requires a new
frontend build. The deployed browser calls Render directly; Vercel's SPA rewrite
is not a backend API proxy. No Render blueprint or CI workflow is checked in.

## Current limitations

- Custom-FEN PGNs can be parsed, but the review tree root and history replay
  assume the standard initial position. Do not claim end-to-end setup-position
  or variant support. Only the parsed main line is engine-reviewed; PGN
  variations are not imported as branches.
- Frontend PGN checks are stronger than backend validation. The backend reads
  the first game and does not explicitly reject parser errors or extra games;
  the analysis request has no PGN-length or game-ply cap. Authentication limits
  access, but there is no per-token compute quota or analysis rate limiter.
- The public health endpoint can start the engine and exposes its path and
  error text. Authentication throttling and caches are process-local, with no
  eviction; they are not distributed controls.
- Variation input auto-selects queen promotion. Failed variation nodes are
  retained; returning to an existing child does not automatically retry its
  request, including after reauthentication.
- There is no application-level cancellation, whole-request deadline, durable
  job, or automatic stream reconnect. Streaming progress does not guarantee
  that a long game or coaching request fits a host/proxy timeout.
- Reviews and variation trees live in React memory and disappear on reload.
  Only the auth token is kept in browser session storage.

# Project Instructions for AI Coding Agents

Canonical instructions for this repository. `CLAUDE.md` points here; keep shared
rules and implementation guidance in this file instead of duplicating them.
Implementation snapshot checked on 2026-11-22. Recheck the cited source files
before making a change: this document is a map, not a replacement for code.

Read [README.md](README.md) for setup, configuration, API contracts, deployment,
and known limitations. When implementation changes, update the affected sections
of both documents in the same change. Describe unimplemented ideas as proposals,
never as existing behavior.

## Role

Act like a senior software engineer on this project, not an order-taker. Bring your own judgment, push back when something seems off, and take responsibility for the technical decisions you make — don't build something you think is wrong just because it was suggested that way.

## Before Building Anything Non-Trivial

Follow this sequence for any new feature, refactor, or change that isn't a trivial fix:

1. **Check for ambiguity.** If the requirements are genuinely unclear, or there's a real trade-off to make (performance vs. simplicity, cost, latency, data model choices, etc.), ask specific clarifying questions before writing any code. Don't ask reflexively for things that are already clear — use judgment.
2. **If there are multiple valid ways to build it, present 2-3 options** with a short trade-off summary for each (complexity, cost, performance, time-to-build, maintainability). Let the answer decide which to build — don't default to the first idea or to whatever was implied in the request.
3. **If you disagree with the direction I've asked for**, say so once, explain why, and propose the alternative — then proceed with my choice if I confirm it. Don't silently comply against your own judgment, and don't relitigate it after I've decided.
4. **Give a short plan before implementing** (files/areas touched, approach) for anything non-trivial, and wait for a go-ahead. Trivial changes (typo fixes, formatting, an isolated single-line fix with an obvious cause) can proceed without this.
5. **Never run destructive or irreversible actions** (force-push, deleting data, altering/resetting migrations, deleting branches) without explicit confirmation, even mid-approved-plan.



## Testing

- Every new feature or bug fix needs tests (unit and/or integration, matching whatever pattern already exists in that part of the codebase).
- Before declaring a task done: actually run the relevant test suite (not just the new tests — anything the change could plausibly affect) and report the real pass/fail result.
- If a workaround papers over a failing test instead of fixing the root cause, say so explicitly rather than presenting it as solved.
- If a part of the codebase has no test setup yet, flag it and propose a minimal one rather than adding untested code to it silently.



## Code Style & Conventions

- Read enough of the surrounding code before writing new code to match existing naming, formatting, structure, and idioms.
- Don't silently introduce a new library, pattern, or architecture in place of what's already used. Implement using existing conventions, and if you think there's a better way, note it separately (e.g. "Suggestion (not applied):") rather than just doing it.
- Keep changes scoped to the task — no opportunistic unrelated refactors in the same diff; mention them as follow-ups instead.



## Project Context: Chess Game Reviewer

This is a chess game analysis/review app (in the spirit of chess.com's Game Review) — takes a played game and produces move-by-move evaluation, move classifications (blunder/mistake/inaccuracy/good/best/brilliant, etc.), and accuracy scoring.

- **Frontend:** deployed on Vercel
- **Backend:** deployed on Render

These architecture choices are already implemented:

- **Engine:** server-side native Stockfish through `python-chess`. The browser
  uses `chess.js` for PGN preview and legal moves, not engine evaluation. No WASM
  engine is present.
- **Requests:** FastAPI synchronous route handlers. Full-game analysis returns
  a POST response streamed as SSE; position and single-move review return JSON.
  There is no job queue, polling API, or resumable analysis job.
- **Concurrency:** `AnalysisService` owns a lazily started engine and a timed
  lock per Python process. Search operations serialize through that service;
  do not create a new engine per request. Multiple workers would have separate
  engines, caches, and authentication throttles.
- **Caching:** whole-game engine results and coaching are cached in process
  memory. Position and single-move engine searches have no application-level
  result cache. See the precise keys and limitations in the README.
- **Hosting:** Vite serves the SPA locally and proxies `/api`; a production
  frontend calls the Render backend origin directly using `VITE_API_BASE_URL`.
  There is no Vercel serverless analysis function in this repository.

Changing these choices requires an explicit design discussion. For hosting
changes, verify current provider limits and the actual deployment tier; this
repository does not establish live timeout, resource, or cold-start guarantees.

## Implementation Map

| Area | Source of truth | Existing tests |
| --- | --- | --- |
| Routes, SSE envelope, CORS, request validation | [backend/main.py](backend/main.py) | `test_auth.py`, `test_analysis_response.py` |
| Token signing and verification | [backend/auth.py](backend/auth.py) | `test_auth.py` |
| Engine lifecycle, locking, game cache | [backend/analysis_service.py](backend/analysis_service.py) | `test_analysis_service.py` |
| Environment defaults and binary discovery | [backend/config.py](backend/config.py) | Service and deployment tests cover selected behavior |
| Search, classifications, facts, accuracy | [backend/engine.py](backend/engine.py) | `test_classify.py`, `test_engine_facts.py` |
| Gemini prompts, validation, fallback prose | [backend/coach.py](backend/coach.py) | `test_coach.py` |
| Opening names and Book eligibility | [backend/openings.py](backend/openings.py) | `test_openings.py` |
| Production engine installation | [backend/Dockerfile](backend/Dockerfile) | `test_deployment.py` (text assertions, not an image build) |
| Review state, authentication replay, variations | [frontend/src/App.tsx](frontend/src/App.tsx), [moveTree.ts](frontend/src/moveTree.ts) | `App.test.tsx`; no dedicated move-tree suite |
| PGN input, preview, opening lookup, status | [AnalyzeForm.tsx](frontend/src/components/AnalyzeForm.tsx), [GameStatusSlot.tsx](frontend/src/components/GameStatusSlot.tsx), [pgnPreview.ts](frontend/src/pgnPreview.ts), [openingLookup.ts](frontend/src/openingLookup.ts) | `AnalyzeForm.test.tsx`, `pgnPreview.test.ts` |
| Board, navigation, evaluation orientation | [ReviewBoard.tsx](frontend/src/components/ReviewBoard.tsx), [MoveNav.tsx](frontend/src/components/MoveNav.tsx), [EvalBar.tsx](frontend/src/components/EvalBar.tsx) | Colocated component tests |
| HTTP clients and frontend response types | [frontend/src/api/client.ts](frontend/src/api/client.ts), [auth.ts](frontend/src/api/auth.ts), [types.ts](frontend/src/types.ts) | App/component mocks; no dedicated client suite |

Backend test filenames above are under `backend/tests/`; frontend tests are
colocated with their subjects. Styling uses Tailwind plus `frontend/src/index.css`.
There is no router, global state library, database, or ORM in the current app.

## Contracts and Invariants

- API depth defaults to `ANALYSIS_DEPTH` (16), with request bounds 8–22. The UI
  and client helpers independently default to 16; changing the environment
  variable does not change the UI slider. Some low-level engine functions still
  default to 18; production callers pass the configured/requested depth.
- Game and move reviews use adaptive MultiPV=2 searches. Selected positions
  deepen to the requested depth; not every position receives that depth.
  Sacrifice verification can add a restricted MultiPV=1 search. Preserve reuse
  of adjacent position searches and the one-move delay in progress emission.
- Classifications are this project's heuristics, not an exact implementation
  of another chess site's labels. Precedence in `classify_move` is mate → Book →
  Blunder/Mistake/Inaccuracy → Miss → Brilliant → Great → Good/Excellent/Best.
  Great requires the exact engine-best move, a unique-best gap, multiple legal
  choices, and the non-obvious-move checks. Brilliant requires the exact best
  move and verified non-pawn material investment; do not substitute a negative
  static exchange score alone for verification.
- Book detection uses UCI sequence prefixes, capped at 12 plies, and the review
  pipeline additionally requires `abs(post_move_mover_cp) < 80`. Opening names
  use the longest named prefix without that cap. Neither lookup is a FEN or
  transposition index.
- `eval_cp_white` and display `eval` are White-relative; `facts.eval_before`
  and `facts.eval_after` are mover-relative pawn values. `hist` is White-relative
  pawns clipped to ±10, with an initial zero. Classification and accuracy use
  different win-expectancy functions; do not merge them casually.
- `MoveData.ply` and critical-moment `ply` are zero-based move indices. SSE
  progress counts completed plies starting at 1. `MoveNode.ply` counts positions
  from root 0. `move_number` is derived from the ply index.
- `fen_before` is before the move; `fen` is after it. Top-level `best_move`,
  `best_uci`, and `played_move` are UCI, while `facts.best` and PV text are SAN.
  Full-game and variation reviews share `_build_move_entry`; preserve their
  response shape and update frontend types when changing it. `MoveFacts` is a
  subset of emitted backend facts, not a generated exhaustive schema.
- SSE is consumed with POST `fetch` and a stream reader, not `EventSource`.
  The frontend consumes progress counts, then builds the review on `complete`;
  it does not add streamed move entries to the board incrementally. Errors
  after streaming begins are `error` events, even with HTTP status 200.
- Gemini writes prose from supplied facts. The current model ID is the
  `DEFAULT_GEMINI_MODEL` constant in `coach.py`; there is no model environment
  variable. Validation is heuristic, not proof that every sentence is correct.
  Preserve deterministic fallbacks and SAN-only references without move numbers.
- `commentary_succeeded` means the generated summary and all requested comments
  passed validation. `all_comments_succeeded` is a compatibility alias.
  `commentary_status.generation_complete` tracks output completeness separately.
  The preview's Gemini success text uses attempted + complete generation, so it
  may show success when some text was replaced. Engine review can complete with
  fallback coaching. Do not conflate these outcomes.
- The review is side-neutral: there is no `player_color` request field or color
  selector. Board orientation is separate UI state, preserved through navigation
  and reset to White at the bottom after a successful new analysis.
- Variation history excludes the move under review. Previous-capture context
  is trusted only when replay from the standard start exactly matches the FEN.
  The tree root is hard-coded to the standard start: custom-FEN PGNs are not
  supported consistently end to end. UI promotions currently select a queen.

## Assets and Generated Data

- [backend/tools/build_openings.py](backend/tools/build_openings.py) generates
  `backend/data/openings.tsv`. The browser separately loads
  `frontend/public/data/openings.tsv`; the generator does not sync it. Regenerate
  once and copy that result when intentionally updating the dataset. Do not
  hand-edit either table. The checked-in tables have the same parsed entries.
- Runtime piece images come from `frontend/public/pieces/`; root `pieces/` is
  a separate artwork copy. Classification icons are served by the backend's
  fixed route mapping. Preserve the uppercase extension of `Inaccuracy.PNG`.
- The root Linux `stockfish` file uses Git LFS. Windows discovery checks
  `stockfishw.exe`, `stockfish.exe`, then `stockfish-windows-x86-64.exe`; the
  local Windows binary is not a portable deployment artifact.

## Verification Commands

Run from the repository root with dependencies installed:

```powershell
.venv\Scripts\python.exe -m pytest
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

On macOS/Linux use `.venv/bin/python -m pytest`. The frontend build runs
`tsc -b && vite build`; tests use Vitest, jsdom, and Testing Library. There is
no configured lint script or backend type-checker. Do not invent commands such
as `npm run lint`. Tests use engine/client doubles and do not certify live
Stockfish strength, Gemini access, a Docker build, or a deployed service.

## Verification Before Reporting Done

- Never assume a library, function, or API exists — check the codebase or package manifest before using it.
- Read files fully before editing them rather than inferring from filenames or partial context.
- After changes: run tests, run the linter/type-checker/build if one exists, and only then report completion — with what you actually ran and the actual result.



## Communication

- Plans before non-trivial work: brief, concrete, list files/areas touched.
- Summaries after work: what changed and why — not a step-by-step narration of every action taken.
- Surface uncertainty and trade-offs explicitly instead of quietly picking one and moving on.



## Security

- Never commit secrets, API keys, tokens, or credentials (careful with `.env` here).
- Proactively flag likely security issues you notice (injection risks, missing auth checks, unsafe deserialization, unvalidated input) even if fixing them wasn't the ask.



## Git

- Don't commit or push unless explicitly asked to.
- If asked to commit, write a clear, scoped commit message describing the actual change.

---


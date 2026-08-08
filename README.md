# AI Chess Game Reviewer

A chess.com-style game review app built on Streamlit + Stockfish + Gemini.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI: review mode + live variation explorer |
| `engine.py` | All chess analysis. **Stockfish is the only source of truth.** |
| `coach.py` | Turns engine-verified facts into text (templates + one Gemini call) |
| `board.py` | chess.com-style HTML/CSS board renderer |
| `pieces.py` | The 12 chess pieces, embedded (open-source cburnett set) |
| `packages.txt` | Installs Stockfish when deploying on Streamlit Cloud |
| `requirements.txt` | Python deps |

Run locally: `streamlit run app.py`

---

## How each of your five requests was addressed

**1. Coach comments that don't hallucinate.**
The old design sent Gemini only `{move, eval, classification}`. With no idea what
was on the board, it invented plausible-but-false reasons ("the rook is attacked").
Now `engine.py` computes every fact from python-chess + Stockfish first — the
engine's preferred move, what is *actually* hanging (verified with a static
exchange evaluation), whether the move was a capture/check/castle, and the
opponent's concrete refutation. Gemini receives only those verified facts and is
instructed to *rephrase* them and invent nothing. It literally cannot say a piece
is hanging unless the engine confirmed it is. Example output on a real blunder:
*"It leaves your pawn on f7 undefended. The opponent can answer with Qxf7#. g6 was stronger."*

**2. Removed the "Show Full Move List" bar.**
Gone. In its place is an integrated, chess.com-style move list in the review panel
with per-move classification badges and the current move highlighted.

**3. Real-time analysis of variations / different lines.**
There's a **Live Variation Explorer**. From any position in the game, branch off
and play whatever moves you like — click the engine's top suggestions or pick any
legal move — and Stockfish re-analyzes *live*, showing the new evaluation, the top
lines, and a best-move arrow. Undo or reset back to the game at any time.

**4. Keep Gemini usage tiny (free tier).**
Ordinary moves get truthful, locally-generated comments with **no API call**.
Only "notable" moves (blunders, mistakes, brilliancies, etc.) are sent to Gemini,
batched into **a single request per game**, and the result is cached — reopening a
game costs zero calls. The variation explorer never calls Gemini at all. If the key
is missing or a call fails, the app falls back to the built-in templates instead of
breaking.

**5. Looks like chess.com.**
Green board (`#EBECD0` / `#779556`), an evaluation bar, move badges, a coach speech
bubble, an evaluation graph, and clean pieces. The pieces are the open-source
**cburnett** set (by Colin M.L. Burnett, via Wikimedia; BSD/GPL/GFDL) — deliberately
*not* chess.com's proprietary artwork, but very close in clarity. They're embedded
directly in `pieces.py`, so nothing loads from an external image host.

---

## Setup

### Stockfish
- **Locally:** put your Stockfish binary next to `app.py`. On Windows name it
  `stockfish.exe`; on macOS/Linux name it `stockfish`.
- **Streamlit Community Cloud (Linux):** your local Windows/Mac binary will *not*
  run there. The included `packages.txt` (containing `stockfish`) makes the platform
  install a Linux build automatically — `app.py` finds it via `shutil.which`. (If you
  prefer, commit a Linux x86-64 Stockfish binary instead.)

### Gemini key
Add your key to Streamlit secrets (`.streamlit/secrets.toml` locally, or the
Secrets box in Streamlit Cloud):

```toml
GEMINI_API_KEY = "your-key-here"
```

The app also reads `GEMINI_API_KEY` from the environment. Without a key it still
works fully using the built-in comment templates.

---

## Notes / possible next steps
- Analysis depth is set to 12 in `app.py` (`DEPTH`) — a good speed/quality balance
  for the free tier. Raise it for stronger analysis at the cost of time.
- Opening moves are labeled "Book" heuristically (first few moves, near-equal). If
  you want true opening names, wire in a small opening database.
- Promotions in the explorer auto-queen; a promotion picker could be added.
- Board click-to-move was intentionally left out: on Streamlit it requires a full
  page reload that wipes the analysis, so the explorer uses buttons/dropdowns, which
  are reliable. A true click-to-move board would need a custom Streamlit component.

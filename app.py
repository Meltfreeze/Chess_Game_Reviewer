"""
app.py — AI Chess Game Reviewer (chess.com-style).

Features:
  * Verified-fact coaching (engine.py + coach.py) so comments never hallucinate.
  * chess.com-style green board with clean pieces (board.py + pieces.py).
  * Step-through review with eval bar, badges, coach bubble and a clickable move list.
  * A LIVE variation explorer: branch off any position and get real-time Stockfish
    lines/eval, with zero extra Gemini calls (protects a free-tier key).

Run:  streamlit run app.py
Needs a Stockfish binary (see get_engine_path) and a GEMINI_API_KEY secret.
"""

import os
import platform
import shutil
import math

import chess
import streamlit as st

import engine as eng
import coach as coach_mod
from board import render_board, BADGE

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
st.set_page_config(page_title="AI Chess Reviewer", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_engine_path():
    """Local binary in the project folder first, then a system install."""
    candidates = []
    if platform.system() == "Windows":
        candidates += ["stockfish.exe", "stockfishw.exe", "stockfish-windows-x86-64.exe"]
    else:
        candidates += ["stockfish", "stockfish-ubuntu-x86-64", "stockfish-linux"]
    for name in candidates:
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            if platform.system() != "Windows":
                try:
                    os.chmod(p, 0o755)
                except OSError:
                    pass
            return p
    found = shutil.which("stockfish")          # packages.txt install on Streamlit Cloud
    return found


ENGINE_PATH = get_engine_path()

def _get_secret(name):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


API_KEY = _get_secret("GEMINI_API_KEY")
gemini_client = None
if API_KEY:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=API_KEY)
    except Exception as e:
        st.warning(f"Gemini disabled ({e}). Coaching will use built-in templates.")

DEPTH = 12          # keep modest: fast + free-tier friendly


# --------------------------------------------------------------------------
# Cached heavy work
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def run_full_analysis(pgn_str, depth):
    return eng.analyze_game(pgn_str, ENGINE_PATH, depth=depth)


@st.cache_data(show_spinner=False)
def analyse_fen_cached(fen, depth):
    return eng.analyse_fen(fen, ENGINE_PATH, depth=depth, multipv=3)


def accuracy_from_acpl(acpl):
    return round(max(10, min(99, 100 * (0.98 ** acpl))))


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
ss = st.session_state
ss.setdefault("ready", False)
ss.setdefault("view_ply", 0)          # 0 = starting position
ss.setdefault("flipped", False)
ss.setdefault("exploring", False)
ss.setdefault("ex_fens", [])
ss.setdefault("ex_sans", [])
ss.setdefault("ex_sel", None)


def enter_explore(start_fen):
    ss.exploring = True
    ss.ex_fens = [start_fen]
    ss.ex_sans = []
    ss.ex_sel = None


def leave_explore():
    ss.exploring = False
    ss.ex_sel = None


def play_explore_move(uci):
    b = chess.Board(ss.ex_fens[-1])
    mv = chess.Move.from_uci(uci)
    if mv in b.legal_moves:
        san = b.san(mv)
        b.push(mv)
        ss.ex_fens.append(b.fen())
        ss.ex_sans.append(san)
        ss.ex_sel = None


def _find_move(board, frm, to):
    for mv in board.legal_moves:
        if mv.from_square == frm and mv.to_square == to:
            if mv.promotion and mv.promotion != chess.QUEEN:
                continue                      # auto-queen
            return mv
    return None


# --------------------------------------------------------------------------
# Sidebar / input
# --------------------------------------------------------------------------
st.markdown("## ♟️ AI Chess Game Reviewer")

if ENGINE_PATH is None:
    st.error(
        "Stockfish not found. Put the binary next to app.py (named `stockfish` / "
        "`stockfish.exe`), or add a `packages.txt` containing `stockfish` when "
        "deploying on Streamlit Cloud."
    )

with st.expander("➕ Analyze a new game", expanded=not ss.ready):
    player_color = st.radio("Your color", ("White", "Black"), horizontal=True,
                            key="player_color")
    pgn_input = st.text_area("Paste PGN", height=140, key="pgn_input")
    if st.button("Review Game", type="primary", disabled=(ENGINE_PATH is None)):
        if not pgn_input.strip():
            st.warning("Paste a PGN first.")
        else:
            try:
                with st.spinner("Stockfish is analyzing every move..."):
                    md, stats, meta, hist = run_full_analysis(pgn_input, DEPTH)
                with st.spinner("Coach is writing your review..."):
                    summary, comments = coach_mod.generate_coach(
                        md, player_color, gemini_client)
                ss.move_data = md
                ss.stats = stats
                ss.meta = meta
                ss.hist = hist
                ss.summary = summary
                ss.comments = comments
                ss.ready = True
                ss.view_ply = 0
                ss.flipped = (player_color == "Black")
                leave_explore()
                st.rerun()
            except Exception as e:
                st.error(f"Could not analyze game: {e}")

if not ss.ready:
    st.info("Paste a PGN above and press **Review Game** to begin.")
    st.stop()


# --------------------------------------------------------------------------
# Data for the current view
# --------------------------------------------------------------------------
md = ss.move_data
meta = ss.meta
stats = ss.stats
n = len(md)
ply = min(ss.view_ply, n)

if ply == 0:
    cur_fen = chess.STARTING_FEN
    last_uci = None
    cur_cp_white = 0
    cur = None
else:
    cur = md[ply - 1]
    cur_fen = cur["fen"]
    last_uci = cur["uci"]
    cur_cp_white = cur["eval_cp_white"]


# --------------------------------------------------------------------------
# Header: player accuracy / rating (chess.com-style)
# --------------------------------------------------------------------------
h1, h2, h3 = st.columns([1, 1, 0.5])
with h1:
    st.markdown(f"**⚪ {meta['White']}** ({meta['WhiteElo']})")
    st.markdown(f"Accuracy **{accuracy_from_acpl(stats['White']['acpl'])}** · "
                f"Est. **{stats['White']['rating']}**")
with h2:
    st.markdown(f"**⚫ {meta['Black']}** ({meta['BlackElo']})")
    st.markdown(f"Accuracy **{accuracy_from_acpl(stats['Black']['acpl'])}** · "
                f"Est. **{stats['Black']['rating']}**")
with h3:
    st.button("🔄 Flip", on_click=lambda: ss.__setitem__("flipped", not ss.flipped),
              use_container_width=True)

st.divider()

board_col, panel_col = st.columns([1.15, 1], gap="large")


# --------------------------------------------------------------------------
# LEFT: eval bar + board + nav
# --------------------------------------------------------------------------
def eval_bar_html(cp_white, height=520):
    wp = eng.cp_to_wp(cp_white)                 # 0..1 for white
    white_h = int(wp * height)
    return (
        f'<div style="width:26px;height:{height}px;background:#403e3b;border-radius:4px;'
        f'overflow:hidden;position:relative;box-shadow:inset 0 0 4px rgba(0,0,0,.5);">'
        f'<div style="position:absolute;bottom:0;width:100%;height:{white_h}px;'
        f'background:#f5f5f0;transition:height .2s;"></div></div>')


with board_col:
    bar_c, brd_c = st.columns([0.09, 1])
    with bar_c:
        st.markdown(eval_bar_html(cur_cp_white), unsafe_allow_html=True)
    with brd_c:
        badge = cur["classification"] if cur else None
        arrow = None
        # show the engine's preferred move as an arrow when the player erred
        if cur and cur["classification"] in ("Blunder", "Mistake", "Inaccuracy"):
            fb = md[ply - 1]["fen_before"]
            best = analyse_fen_cached(fb, DEPTH)[0]["first_uci"]
            arrow = best
        html = render_board(cur_fen, size=520, flipped=ss.flipped,
                            last_move_uci=last_uci, badge_class=badge,
                            arrow_uci=arrow, clickable=False)
        st.markdown(html, unsafe_allow_html=True)

    # navigation (buttons + scrubber — all state-preserving Streamlit widgets)
    ss.view_ply = min(ss.view_ply, n)          # clamp before the slider widget
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.button("⏮", on_click=lambda: ss.__setitem__("view_ply", 0),
              use_container_width=True, disabled=(ply == 0))
    c2.button("◀", on_click=lambda: ss.__setitem__("view_ply", max(0, ply - 1)),
              use_container_width=True, disabled=(ply == 0))
    c3.markdown(f"<div style='text-align:center;padding-top:6px;font-weight:700;'>"
                f"{ply}/{n}</div>", unsafe_allow_html=True)
    c4.button("▶", on_click=lambda: ss.__setitem__("view_ply", min(n, ply + 1)),
              use_container_width=True, disabled=(ply >= n))
    c5.button("⏭", on_click=lambda: ss.__setitem__("view_ply", n),
              use_container_width=True, disabled=(ply >= n))
    if n > 0:
        st.slider("Move", 0, n, key="view_ply", label_visibility="collapsed")


# --------------------------------------------------------------------------
# RIGHT: coach bubble + move list + eval graph + explorer entry
# --------------------------------------------------------------------------
def coach_bubble(text, cls):
    glyph, colour = BADGE.get(cls, ("•", "#8b8987"))
    header = (f'<span style="display:inline-block;background:{colour};color:#fff;'
              f'border-radius:12px;padding:1px 10px;font-weight:800;font-size:13px;">'
              f'{glyph} {cls}</span>') if cls else ""
    return (
        f'<div style="background:#fff;border-radius:14px;padding:14px 16px;'
        f'box-shadow:0 2px 10px rgba(0,0,0,.12);color:#2b2b2b;line-height:1.45;">'
        f'{header}<div style="margin-top:8px;">{text}</div></div>')


with panel_col:
    st.markdown("### ⭐ Game Review")
    if ply == 0:
        st.markdown(coach_bubble(ss.summary, None), unsafe_allow_html=True)
    else:
        comment = ss.comments[ply - 1] if ply - 1 < len(ss.comments) else ""
        st.markdown(coach_bubble(f"<b>{cur['turn']} played {cur['san']}</b> "
                                 f"(eval {cur['eval']}).<br>{comment}",
                                 cur["classification"]), unsafe_allow_html=True)

    # ---- eval graph (SVG area chart) ----
    st.markdown("#### Evaluation")
    hist = ss.hist
    W, H = 100, 46
    pts = []
    for i, v in enumerate(hist):
        x = (i / max(1, len(hist) - 1)) * W
        y = H / 2 - (max(-6, min(6, v)) / 6) * (H / 2)
        pts.append((x, y))
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    area = (f"M0,{H/2} " +
            " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) +
            f" L{W},{H/2} Z")
    mx = pts[min(ply, len(pts) - 1)][0]
    graph = (
        f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" '
        f'style="width:100%;height:70px;background:#403e3b;border-radius:6px;">'
        f'<line x1="0" y1="{H/2}" x2="{W}" y2="{H/2}" stroke="#5c5a57" stroke-width="0.4"/>'
        f'<path d="{area}" fill="#f5f5f0" fill-opacity="0.85"/>'
        f'<path d="{path}" fill="none" stroke="#9c9a97" stroke-width="0.5"/>'
        f'<line x1="{mx:.1f}" y1="0" x2="{mx:.1f}" y2="{H}" stroke="#e58f2a" stroke-width="0.6"/>'
        f'</svg>')
    st.markdown(graph, unsafe_allow_html=True)

    # ---- move list (chess.com-style, current move highlighted) ----
    st.markdown("#### Moves")
    rows = []
    i = 0
    while i < n:
        w = md[i]
        b = md[i + 1] if i + 1 < n else None

        def cell(m, idx):
            if m is None:
                return "<td></td>"
            g, c = BADGE.get(m["classification"], ("", "#666"))
            hl = "background:#4a4844;border-radius:4px;" if (idx + 1) == ply else ""
            return (f'<td style="padding:2px 4px;{hl}color:#e8e8e8;">'
                    f'{m["san"]} <span style="color:{c};font-weight:800;">{g}</span></td>')

        rows.append(f'<tr><td style="color:#8b8987;width:26px;">{w["move_number"]}.</td>'
                    f'{cell(w, i)}{cell(b, i + 1)}</tr>')
        i += 2
    table = (f'<div style="max-height:220px;overflow-y:auto;background:#302e2b;'
             f'border-radius:6px;padding:6px 8px;font-size:14px;">'
             f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table></div>')
    st.markdown(table, unsafe_allow_html=True)

    # ---- explorer entry ----
    st.markdown("---")
    if not ss.exploring:
        st.button("🔍 Explore variations from here", use_container_width=True,
                  on_click=lambda: enter_explore(cur_fen))
    else:
        st.button("✖ Close explorer", use_container_width=True, on_click=leave_explore)


# --------------------------------------------------------------------------
# LIVE VARIATION EXPLORER (real-time Stockfish, no Gemini)
# --------------------------------------------------------------------------
if ss.exploring:
    st.divider()
    st.markdown("### 🔬 Live Variation Explorer")
    st.caption("Click a piece then its destination, or use the buttons below. "
               "Every position is analyzed live by Stockfish — no AI-coach calls used here.")

    ex_fen = ss.ex_fens[-1]
    ex_board = chess.Board(ex_fen)
    lines = analyse_fen_cached(ex_fen, DEPTH)

    ex_col, ex_panel = st.columns([1.15, 1], gap="large")

    with ex_col:
        last = None
        if ss.ex_sans:
            # reconstruct last move uci for highlight
            prev = chess.Board(ss.ex_fens[-2])
            for m in prev.legal_moves:
                if prev.san(m) == ss.ex_sans[-1]:
                    last = m.uci()
                    break
        top_arrow = lines[0]["first_uci"] if lines else None
        html = render_board(ex_fen, size=520, flipped=ss.flipped,
                            last_move_uci=last, arrow_uci=top_arrow,
                            clickable=False)
        st.markdown(html, unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        b1.button("↩ Undo move", use_container_width=True,
                  disabled=(len(ss.ex_fens) <= 1),
                  on_click=lambda: (ss.ex_fens.pop(), ss.ex_sans.pop()))
        b2.button("⟲ Reset to game", use_container_width=True,
                  disabled=(len(ss.ex_fens) <= 1),
                  on_click=lambda: (ss.__setitem__("ex_fens", ss.ex_fens[:1]),
                                    ss.__setitem__("ex_sans", [])))

    with ex_panel:
        turn = "White" if ex_board.turn == chess.WHITE else "Black"
        top_eval = lines[0]["eval"] if lines else "?"
        st.markdown(f"**{turn} to move — engine eval {top_eval}**")
        if ss.ex_sans:
            st.markdown("**Your line:** " + " ".join(ss.ex_sans))

        st.markdown("**Top engine moves** (click to play):")
        for k, ln in enumerate(lines):
            if not ln["first_uci"]:
                continue
            first_san = ln["san_line"][0] if ln["san_line"] else ln["first_uci"]
            line_txt = " ".join(ln["san_line"])
            st.button(f'{first_san}   ({ln["eval"]})   —   {line_txt}',
                      key=f"eng_{k}_{len(ss.ex_fens)}",
                      use_container_width=True,
                      on_click=play_explore_move, args=(ln["first_uci"],))

        # full legal-move fallback (always works, even if clicks don't)
        with st.expander("Or pick any legal move"):
            legal = sorted(ex_board.san(m) for m in ex_board.legal_moves)
            choice = st.selectbox("Legal moves", legal, key=f"legal_{len(ss.ex_fens)}")
            if st.button("Play move", key=f"playlegal_{len(ss.ex_fens)}"):
                mv = ex_board.parse_san(choice)
                play_explore_move(mv.uci())
                st.rerun()

        if ex_board.is_checkmate():
            st.success("Checkmate!")
        elif ex_board.is_stalemate():
            st.info("Stalemate.")

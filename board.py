"""
board.py — Renders a chess.com-style board as pure HTML/CSS (no JS needed).

Colours match chess.com's green theme; pieces are the open-source cburnett set
embedded in pieces.py. Squares can optionally be clickable links that set a
`?click=<square>` query param, which app.py reads to drive click-to-move.
"""

import chess
from pieces import PIECE_SVG

LIGHT = "#EBECD0"
DARK = "#779556"
LAST = "#F6F669"          # last-move highlight (chess.com yellow)
LAST_D = "#BACA2B"
SEL = "#F7EC74"           # selected square
CHECK = "#EB7D6A"         # king in check

# classification -> (glyph, colour) for the little badge on the moved square
BADGE = {
    "Brilliant": ("!!", "#1BADA6"),
    "Great":     ("!",  "#5C8BB0"),
    "Best":      ("★",  "#95BB4A"),
    "Excellent": ("✓",  "#95BB4A"),
    "Good":      ("✓",  "#96AF8B"),
    "Book":      ("♘",  "#A88865"),
    "Inaccuracy":("?!", "#F0C15C"),
    "Mistake":   ("?",  "#E58F2A"),
    "Miss":      ("✗",  "#EE6B55"),
    "Blunder":   ("??", "#CA3431"),
}


def _piece_key(piece):
    c = "w" if piece.color == chess.WHITE else "b"
    s = piece.symbol().upper()
    return f"{c}{s}"


def render_board(fen, size=520, flipped=False, last_move_uci=None,
                 selected=None, legal_targets=None, arrow_uci=None,
                 badge_class=None, clickable=False):
    board = chess.Board(fen)
    sq = size / 8
    legal_targets = set(legal_targets or [])

    last_from = last_to = None
    if last_move_uci:
        mv = chess.Move.from_uci(last_move_uci)
        last_from, last_to = mv.from_square, mv.to_square

    check_sq = board.king(board.turn) if board.is_check() else None

    cells = []
    display_rows = range(8)
    for dr in display_rows:
        for dc in range(8):
            if flipped:
                file, rank = 7 - dc, dr
            else:
                file, rank = dc, 7 - dr
            square = chess.square(file, rank)
            is_light = (file + rank) % 2 == 1
            base = LIGHT if is_light else DARK

            # highlight priority: selected > last-move > check
            bg = base
            if square in (last_from, last_to):
                bg = LAST if is_light else LAST_D
            if square == check_sq:
                bg = CHECK
            if square == selected:
                bg = SEL

            inner = ""
            piece = board.piece_at(square)
            if piece:
                inner = (f'<img src="{PIECE_SVG[_piece_key(piece)]}" '
                         f'style="width:100%;height:100%;pointer-events:none;">')

            # legal-move markers (dot for empty, ring for capture)
            marker = ""
            if square in legal_targets:
                if piece:
                    marker = ('<div style="position:absolute;inset:0;border-radius:50%;'
                              'box-shadow:inset 0 0 0 5px rgba(0,0,0,0.28);"></div>')
                else:
                    marker = ('<div style="position:absolute;left:50%;top:50%;'
                              'width:32%;height:32%;transform:translate(-50%,-50%);'
                              'border-radius:50%;background:rgba(0,0,0,0.22);"></div>')

            # coordinate labels (chess.com puts them in board corners)
            coord = ""
            label_col = DARK if is_light else LIGHT
            if dc == 0:
                coord += (f'<span style="position:absolute;left:2px;top:1px;font-size:11px;'
                          f'font-weight:700;color:{label_col};">{rank+1}</span>')
            if dr == 7:
                coord += (f'<span style="position:absolute;right:2px;bottom:0px;font-size:11px;'
                          f'font-weight:700;color:{label_col};">{"abcdefgh"[file]}</span>')

            # classification badge on the destination square
            badge = ""
            if badge_class and square == last_to and badge_class in BADGE:
                glyph, colour = BADGE[badge_class]
                badge = (f'<div style="position:absolute;top:-6px;right:-6px;width:22px;'
                         f'height:22px;border-radius:50%;background:{colour};color:#fff;'
                         f'font-size:12px;font-weight:800;line-height:22px;text-align:center;'
                         f'box-shadow:0 1px 3px rgba(0,0,0,.4);z-index:6;">{glyph}</div>')

            content = f"{coord}{inner}{marker}{badge}"
            style = (f"position:relative;width:{sq}px;height:{sq}px;background:{bg};"
                     f"display:flex;align-items:center;justify-content:center;")
            if clickable:
                cells.append(
                    f'<a href="?click={chess.square_name(square)}" target="_self" '
                    f'style="{style}text-decoration:none;">{content}</a>')
            else:
                cells.append(f'<div style="{style}">{content}</div>')

    grid = (f'<div style="display:grid;grid-template-columns:repeat(8,{sq}px);'
            f'grid-template-rows:repeat(8,{sq}px);width:{size}px;height:{size}px;'
            f'border-radius:5px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.35);">'
            f'{"".join(cells)}</div>')

    # best-move arrow overlay
    arrow = ""
    if arrow_uci:
        mv = chess.Move.from_uci(arrow_uci)

        def center(s):
            f, r = chess.square_file(s), chess.square_rank(s)
            dc = (7 - f) if flipped else f
            dr = r if flipped else (7 - r)
            return (dc + 0.5) * sq, (dr + 0.5) * sq

        x1, y1 = center(mv.from_square)
        x2, y2 = center(mv.to_square)
        arrow = (
            f'<svg width="{size}" height="{size}" style="position:absolute;left:0;top:0;'
            f'pointer-events:none;z-index:5;"><defs>'
            f'<marker id="ah" markerWidth="4" markerHeight="4" refX="2" refY="2" orient="auto">'
            f'<path d="M0,0 L4,2 L0,4 z" fill="#11772d"/></marker></defs>'
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#11772d" '
            f'stroke-width="{sq*0.16}" stroke-opacity="0.75" stroke-linecap="round" '
            f'marker-end="url(#ah)"/></svg>')

    return (f'<div style="position:relative;width:{size}px;height:{size}px;">'
            f'{grid}{arrow}</div>')

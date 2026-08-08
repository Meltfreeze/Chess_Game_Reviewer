"""
engine.py — All chess analysis. Stockfish is the ONLY source of chess truth.

The important idea: every "fact" that the coach is allowed to talk about is
computed here from python-chess + Stockfish. The language model never sees the
board and never decides what is happening on it, so it cannot hallucinate
"the rook is attacked" when nothing is attacked.
"""

import io
import chess
import chess.pgn
import chess.engine

VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}
NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}
BACK_RANK = {chess.WHITE: 7, chess.BLACK: 0}


# --------------------------------------------------------------------------
# Static Exchange Evaluation (used to know if a piece is *really* hanging /
# if a move is a real sacrifice). This is verified material math, not a guess.
# --------------------------------------------------------------------------
def _promoted_type(piece_type, color, square, forced_promotion=None):
    if piece_type == chess.PAWN and chess.square_rank(square) == BACK_RANK[color]:
        return forced_promotion or chess.QUEEN
    return piece_type


def _least_valuable_attacker(board, square, color):
    attackers = board.attackers(color, square)
    if not attackers:
        return None

    def sort_value(sq):
        p = board.piece_at(sq)
        return VALUES[_promoted_type(p.piece_type, p.color, square)]

    for sq in sorted(attackers, key=sort_value):
        piece = board.piece_at(sq)
        if piece.piece_type == chess.KING:
            if board.attackers(not color, square):
                continue
        elif square not in board.pin(color, sq):
            continue
        return sq
    return None


def static_exchange_eval(board, move):
    to_sq, from_sq = move.to_square, move.from_square
    mover = board.piece_at(from_sq)
    if mover is None:
        return 0
    scratch = board.copy(stack=False)

    if board.is_en_passant(move):
        captured_sq = chess.square(chess.square_file(to_sq), chess.square_rank(from_sq))
        gain = [VALUES[chess.PAWN]]
        scratch.remove_piece_at(captured_sq)
    else:
        captured = scratch.piece_at(to_sq)
        gain = [VALUES.get(captured.piece_type, 0) if captured else 0]

    mover_type = _promoted_type(mover.piece_type, mover.color, to_sq, move.promotion)
    attacker_value = VALUES[mover_type]
    side = not mover.color

    scratch.remove_piece_at(from_sq)
    scratch.set_piece_at(to_sq, chess.Piece(mover_type, mover.color))

    depth = 0
    while True:
        attacker_sq = _least_valuable_attacker(scratch, to_sq, side)
        if attacker_sq is None:
            break
        depth += 1
        gain.append(attacker_value - gain[depth - 1])
        ap = scratch.piece_at(attacker_sq)
        at = _promoted_type(ap.piece_type, ap.color, to_sq)
        attacker_value = VALUES[at]
        scratch.remove_piece_at(attacker_sq)
        scratch.set_piece_at(to_sq, chess.Piece(at, ap.color))
        side = not side

    while depth:
        gain[depth - 1] = -max(-gain[depth - 1], gain[depth])
        depth -= 1
    return gain[0]


def is_sacrifice(board, move):
    if not board.piece_at(move.from_square):
        return False
    if not board.attackers(not board.turn, move.to_square):
        return False
    return static_exchange_eval(board, move) < 0


# --------------------------------------------------------------------------
# Win probability + classification
# --------------------------------------------------------------------------
def cp_to_wp(cp):
    cp = max(-10000, min(10000, cp))
    return 1 / (1 + 10 ** (-cp / 400))


def classify_move(prev_cp, curr_cp, is_only_move, is_sac, is_book, is_mate=False):
    """prev_cp / curr_cp are from the MOVER's point of view (centipawns)."""
    if is_mate:                       # delivering checkmate is never a mistake
        return "Brilliant" if is_sac else "Best"
    if is_book:
        return "Book"
    wp_loss = cp_to_wp(prev_cp) - cp_to_wp(curr_cp)

    if wp_loss >= 0.20:
        return "Blunder"
    if wp_loss >= 0.12:
        return "Mistake"
    if wp_loss >= 0.06:
        return "Inaccuracy"
    if wp_loss >= 0.03:
        return "Good"
    if wp_loss >= 0.02:
        return "Excellent"
    # essentially the top move
    if is_sac and cp_to_wp(curr_cp) > 0.20:
        return "Brilliant"
    if is_only_move and cp_to_wp(curr_cp) > 0.10:
        return "Great"
    return "Best"


NOTABLE = {"Blunder", "Mistake", "Inaccuracy", "Brilliant", "Great"}


# --------------------------------------------------------------------------
# Verified fact extraction — everything the coach is allowed to say
# --------------------------------------------------------------------------
def _square_name(sq):
    return chess.square_name(sq)


def _hanging_pieces(board, color):
    """Pieces of `color` that are attacked and lose material by SEE if grabbed.
    Verified — used so the coach only mentions *actually* hanging pieces."""
    out = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != color or piece.piece_type == chess.KING:
            continue
        if not board.attackers(not color, sq):
            continue
        # simulate the opponent's best capture on this square
        best_gain = 0
        for atk in board.attackers(not color, sq):
            cap = chess.Move(atk, sq)
            if board.is_legal(cap):
                best_gain = max(best_gain, static_exchange_eval(board, cap))
        if best_gain > 0:
            out.append((NAMES[piece.piece_type], _square_name(sq), best_gain))
    out.sort(key=lambda x: -x[2])
    return out


def extract_facts(board_before, move, best_move, eval_before_cp, eval_after_cp,
                  classification, opp_reply_san=None):
    """
    Returns (facts_dict, short_prompt_string).
    board_before: position BEFORE the move (mover to move).
    best_move: engine's #1 move in board_before (a chess.Move) or None.
    eval_*_cp: centipawns from the MOVER's perspective.
    opp_reply_san: SAN of opponent's best reply after the move (for refutations).
    Every field is derived from the real board — nothing is inferred by an LLM.
    """
    mover = board_before.turn
    san = board_before.san(move)
    best_san = board_before.san(best_move) if best_move else None

    facts = {
        "played": san,
        "class": classification,
        "eval_before": round(eval_before_cp / 100, 1),
        "eval_after": round(eval_after_cp / 100, 1),
        "is_capture": board_before.is_capture(move),
        "is_check": board_before.gives_check(move),
        "is_castle": board_before.is_castling(move),
        "is_promo": move.promotion is not None,
        "best": best_san if best_san and best_san != san else None,
    }

    # What did the played move leave hanging? (verified)
    after = board_before.copy(stack=False)
    after.push(move)
    hanging_raw = _hanging_pieces(after, mover)  # [(name, sq, gain), ...]
    # Only nag about hanging pieces on dubious moves, or when a real piece
    # (>= a minor) is left en prise — otherwise gambit pawns create noise.
    mistake_class = classification in ("Blunder", "Mistake", "Inaccuracy")
    hanging = [(n, s, g) for (n, s, g) in hanging_raw if mistake_class or g >= 3]
    facts["hanging"] = [f"{n} on {s}" for (n, s, g) in hanging[:2]]

    # If it was a blunder/mistake, what is the opponent's concrete refutation?
    facts["refutation"] = None
    if classification in ("Blunder", "Mistake") and opp_reply_san:
        facts["refutation"] = opp_reply_san

    # Did the player miss a strong capture / the engine's move?
    facts["missed_best"] = facts["best"]

    # Build a compact prompt string (tiny, to stay within free-tier limits)
    bits = [f'{san} ({classification}, eval {facts["eval_before"]:+}->{facts["eval_after"]:+})']
    if facts["is_castle"]:
        bits.append("castles")
    if facts["is_capture"]:
        bits.append("a capture")
    if facts["is_check"]:
        bits.append("gives check")
    if facts["best"]:
        bits.append(f'engine preferred {facts["best"]}')
    if facts["hanging"]:
        bits.append("leaves hanging: " + ", ".join(facts["hanging"]))
    if facts["refutation"]:
        bits.append(f'opponent can reply {facts["refutation"]}')
    prompt_str = "; ".join(bits)
    return facts, prompt_str


# --------------------------------------------------------------------------
# Full-game analysis
# --------------------------------------------------------------------------
def open_engine(path):
    engine = chess.engine.SimpleEngine.popen_uci(path)
    return engine


def _score_white_cp(info):
    return info["score"].white().score(mate_score=10000)


def _eval_str(pov_white_score):
    if pov_white_score.is_mate():
        return f"#{pov_white_score.mate()}"
    return f"{pov_white_score.score() / 100:+.2f}"


def analyze_game(pgn_str, engine_path, depth=12):
    engine = open_engine(engine_path)
    game = chess.pgn.read_game(io.StringIO(pgn_str))
    if game is None:
        engine.quit()
        raise ValueError("Invalid PGN")

    headers = game.headers
    metadata = {
        "White": headers.get("White", "White"),
        "Black": headers.get("Black", "Black"),
        "WhiteElo": headers.get("WhiteElo", "?"),
        "BlackElo": headers.get("BlackElo", "?"),
        "Result": headers.get("Result", "*"),
    }

    board = game.board()
    limit = chess.engine.Limit(depth=depth)
    prev_info = engine.analyse(board, limit, multipv=2)
    prev_cp_white = _score_white_cp(prev_info[0])

    move_data = []
    eval_history = [0.0]
    total_cp_loss = {chess.WHITE: 0, chess.BLACK: 0}
    counted = {chess.WHITE: 0, chess.BLACK: 0}
    ply = 0

    for game_node in game.mainline():
        move = game_node.move
        mover = board.turn
        board_before = board.copy(stack=False)
        best_move = prev_info[0]["pv"][0] if prev_info[0].get("pv") else None
        san = board.san(move)

        is_sac = is_sacrifice(board, move)
        second_cp_white = (_score_white_cp(prev_info[1])
                           if len(prev_info) > 1 else prev_cp_white)

        board.push(move)
        is_mate_delivered = board.is_checkmate()

        clock_seconds = game_node.clock()
        w_clk_local = clock_seconds if mover == chess.WHITE else (move_data[-1]["w_clk"] if move_data else None)
        b_clk_local = clock_seconds if mover == chess.BLACK else (move_data[-1]["b_clk"] if move_data else None)

        info = engine.analyse(board, limit, multipv=2)
        curr_cp_white = _score_white_cp(info[0])
        pov = info[0]["score"].white()
        eval_history.append(max(-10, min(10, curr_cp_white / 100)))

        # opponent's best reply (for refutations) in SAN
        opp_reply_san = None
        if info[0].get("pv"):
            try:
                opp_reply_san = board.san(info[0]["pv"][0])
            except Exception:
                opp_reply_san = None

        # mover perspective
        if mover == chess.WHITE:
            prev_cp, curr_cp, second_cp = prev_cp_white, curr_cp_white, second_cp_white
        else:
            prev_cp, curr_cp, second_cp = -prev_cp_white, -curr_cp_white, -second_cp_white

        is_only_move = (cp_to_wp(prev_cp) - cp_to_wp(second_cp)) >= 0.20
        is_book = ply < 6 and abs(curr_cp) < 60 and not is_sac
        classification = classify_move(prev_cp, curr_cp, is_only_move,
                                       is_sac, is_book, is_mate_delivered)

        cp_loss = min(1000, max(0, prev_cp - curr_cp))   # cap so one mate != huge ACPL
        total_cp_loss[mover] += cp_loss
        counted[mover] += 1

        facts, prompt_str = extract_facts(
            board_before, move, best_move, prev_cp, curr_cp,
            classification, opp_reply_san)

        move_data.append({
            "ply": ply,
            "move_number": (ply // 2) + 1,
            "turn": "White" if mover == chess.WHITE else "Black",
            "san": san,
            "uci": move.uci(),
            "fen": board.fen(),
            "fen_before": board_before.fen(),
            "eval": _eval_str(pov),
            "eval_cp_white": curr_cp_white,
            "classification": classification,
            "facts": facts,
            "prompt_str": prompt_str,
            "cp_loss": cp_loss,
            "w_clk": w_clk_local,
            "b_clk": b_clk_local,
        })

        prev_info = info
        prev_cp_white = curr_cp_white
        ply += 1

    engine.quit()

    def rating(color):
        if counted[color] == 0:
            return 0, 0
        acpl = total_cp_loss[color] / counted[color]
        r = max(100, round(3100 / (2.718 ** (0.01 * acpl))))
        return r, round(acpl, 1)

    w_rating, w_acpl = rating(chess.WHITE)
    b_rating, b_acpl = rating(chess.BLACK)

    summary_stats = {
        "White": {"rating": w_rating, "acpl": w_acpl},
        "Black": {"rating": b_rating, "acpl": b_acpl},
    }
    return move_data, summary_stats, metadata, eval_history


# --------------------------------------------------------------------------
# Live single-position analysis (for the interactive variation explorer)
# --------------------------------------------------------------------------
def analyse_fen(fen, engine_path, depth=12, multipv=3):
    """Return top-N lines for an arbitrary position. Pure Stockfish, no LLM."""
    engine = open_engine(engine_path)
    board = chess.Board(fen)
    try:
        infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    finally:
        engine.quit()

    lines = []
    for info in infos:
        pov = info["score"].white()
        pv = info.get("pv", [])
        # SAN line
        san_line = []
        tmp = board.copy(stack=False)
        for mv in pv[:6]:
            try:
                san_line.append(tmp.san(mv))
                tmp.push(mv)
            except Exception:
                break
        lines.append({
            "eval": _eval_str(pov),
            "eval_cp_white": pov.score(mate_score=10000),
            "first_uci": pv[0].uci() if pv else None,
            "san_line": san_line,
        })
    return lines

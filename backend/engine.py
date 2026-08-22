"""
engine.py — All chess analysis. Stockfish is the ONLY source of chess truth.
"""

import io
import chess
import chess.pgn
import chess.engine

from backend.openings import lookup_opening, is_book_move
from backend.config import ENGINE_TIME_LIMIT_SECONDS

VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}
NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}
BACK_RANK = {chess.WHITE: 7, chess.BLACK: 0}

NOTABLE = {"Blunder", "Mistake", "Inaccuracy", "Brilliant", "Great", "Miss"}
CRITICAL_CLASSES = {"Blunder", "Brilliant", "Miss", "Mistake"}


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


def cp_to_wp(cp):
    cp = max(-10000, min(10000, cp))
    return 1 / (1 + 10 ** (-cp / 400))


def _game_phase(board, ply):
    piece_count = len(board.piece_map())
    if ply < 20:
        return "opening"
    if piece_count <= 12:
        return "endgame"
    return "middlegame"


def _material_count(board, color):
    total = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type != chess.KING:
            total += VALUES[p.piece_type]
    return total


def is_miss_move(board_before, move, best_move, prev_cp, curr_cp, classification):
    """Detect missed tactical opportunity without huge immediate eval drop."""
    if not best_move or move == best_move:
        return False
    if classification in ("Blunder", "Mistake", "Inaccuracy"):
        return False
    cp_loss = prev_cp - curr_cp
    if cp_loss >= 120:
        return False
    if board_before.is_capture(best_move) and static_exchange_eval(board_before, best_move) > 0:
        if cp_loss >= 60:
            return True
    if cp_loss >= 80 and cp_loss < 120:
        return True
    if prev_cp > 150 and cp_loss >= 50 and best_move != move:
        if board_before.is_capture(best_move):
            return True
    return False


def classify_move(prev_cp, curr_cp, is_only_move, is_sac, is_book, is_mate=False, is_miss=False):
    if is_mate:
        return "Brilliant" if is_sac else "Best"
    if is_miss:
        return "Miss"
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
    if is_sac and cp_to_wp(curr_cp) > 0.20:
        return "Brilliant"
    if is_only_move and cp_to_wp(curr_cp) > 0.10:
        return "Great"
    return "Best"


def _hanging_pieces(board, color):
    out = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != color or piece.piece_type == chess.KING:
            continue
        if not board.attackers(not color, sq):
            continue
        best_gain = 0
        for atk in board.attackers(not color, sq):
            cap = chess.Move(atk, sq)
            if board.is_legal(cap):
                best_gain = max(best_gain, static_exchange_eval(board, cap))
        if best_gain > 0:
            out.append((NAMES[piece.piece_type], chess.square_name(sq), best_gain))
    out.sort(key=lambda x: -x[2])
    return out


def _pv_to_san(board, pv, max_plies=8):
    san_line = []
    tmp = board.copy(stack=False)
    for mv in pv[:max_plies]:
        try:
            san_line.append(tmp.san(mv))
            tmp.push(mv)
        except Exception:
            break
    return san_line


def extract_facts(board_before, move, best_move, eval_before_cp, eval_after_cp,
                  classification, opp_reply_san=None, opening_name=None, phase=None):
    mover = board_before.turn
    san = board_before.san(move)
    best_san = board_before.san(best_move) if best_move else None

    after = board_before.copy(stack=False)
    after.push(move)

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
        "phase": phase or _game_phase(after, 0),
        "opening": opening_name,
    }

    if best_move and best_move != move and board_before.is_capture(best_move):
        see = static_exchange_eval(board_before, best_move)
        if see > 0:
            facts["missed_capture"] = board_before.san(best_move)

    mat_before = _material_count(board_before, mover)
    mat_after = _material_count(after, mover)
    if mat_after < mat_before:
        facts["material_lost"] = mat_before - mat_after

    if classification in ("Blunder", "Mistake") and after.is_check():
        facts["king_in_check"] = True

    mistake_class = classification in ("Blunder", "Mistake", "Inaccuracy", "Miss")
    hanging_raw = _hanging_pieces(after, mover)
    hanging = [(n, s, g) for (n, s, g) in hanging_raw if mistake_class or g >= 3]
    facts["hanging"] = [f"{n} on {s}" for (n, s, g) in hanging[:2]]

    facts["refutation"] = None
    if classification in ("Blunder", "Mistake") and opp_reply_san:
        facts["refutation"] = opp_reply_san

    facts["missed_best"] = facts["best"]

    bits = [f'{san} ({classification}, eval {facts["eval_before"]:+}->{facts["eval_after"]:+})']
    if facts.get("phase"):
        bits.append(f'phase: {facts["phase"]}')
    if facts.get("opening"):
        bits.append(f'opening: {facts["opening"]}')
    if facts["is_castle"]:
        bits.append("castles")
    if facts["is_capture"]:
        bits.append("a capture")
    if facts["is_check"]:
        bits.append("gives check")
    if facts.get("missed_capture"):
        bits.append(f'missed capture {facts["missed_capture"]}')
    if facts["best"]:
        bits.append(f'engine preferred {facts["best"]}')
    if facts.get("material_lost"):
        bits.append(f'lost {facts["material_lost"]} material value')
    if facts.get("king_in_check"):
        bits.append("king exposed to check")
    if facts["hanging"]:
        bits.append("leaves hanging: " + ", ".join(facts["hanging"]))
    if facts["refutation"]:
        bits.append(f'opponent can reply {facts["refutation"]}')
    prompt_str = "; ".join(bits)
    return facts, prompt_str


def _score_white_cp(info):
    return info["score"].white().score(mate_score=10000)


def _eval_str(pov_white_score):
    if pov_white_score.is_mate():
        return f"#{pov_white_score.mate()}"
    return f"{pov_white_score.score() / 100:+.2f}"


def _critical_moments(move_data):
    moments = []
    for i, m in enumerate(move_data):
        eval_swing = abs(m.get("eval_swing", 0))
        if m["classification"] in CRITICAL_CLASSES or eval_swing >= 1.5:
            moments.append({
                "ply": m["ply"],
                "san": m["san"],
                "classification": m["classification"],
                "eval_swing": eval_swing,
            })
    return moments


def analyze_game_streaming(pgn_str, engine, depth=18):
    """Generator yielding (event_type, payload) for SSE streaming."""
    game = chess.pgn.read_game(io.StringIO(pgn_str))
    if game is None:
        raise ValueError("Invalid PGN")

    headers = game.headers
    metadata = {
        "White": headers.get("White", "White"),
        "Black": headers.get("Black", "Black"),
        "WhiteElo": headers.get("WhiteElo", "?"),
        "BlackElo": headers.get("BlackElo", "?"),
        "Result": headers.get("Result", "*"),
        "Opening": headers.get("Opening", ""),
        "ECO": headers.get("ECO", ""),
    }

    board = game.board()
    limit = chess.engine.Limit(depth=depth, time=ENGINE_TIME_LIMIT_SECONDS)
    prev_info = engine.analyse(board, limit, multipv=2)
    prev_cp_white = _score_white_cp(prev_info[0])

    move_data = []
    eval_history = [0.0]
    total_cp_loss = {chess.WHITE: 0, chess.BLACK: 0}
    counted = {chess.WHITE: 0, chess.BLACK: 0}
    uci_history = []
    ply = 0

    eco, opening_name = lookup_opening(uci_history)
    if eco and not metadata["ECO"]:
        metadata["ECO"] = eco
    if opening_name and not metadata["Opening"]:
        metadata["Opening"] = opening_name

    total_moves = sum(1 for _ in game.mainline())

    for game_node in game.mainline():
        move = game_node.move
        mover = board.turn
        board_before = board.copy(stack=False)
        best_move = prev_info[0]["pv"][0] if prev_info[0].get("pv") else None
        best_line = _pv_to_san(board_before, prev_info[0].get("pv", []))
        san = board.san(move)

        is_sac = is_sacrifice(board, move)
        second_cp_white = (_score_white_cp(prev_info[1])
                           if len(prev_info) > 1 else prev_cp_white)

        board.push(move)
        uci_history.append(move.uci())
        is_mate_delivered = board.is_checkmate()

        info = engine.analyse(board, limit, multipv=2)
        curr_cp_white = _score_white_cp(info[0])
        pov = info[0]["score"].white()
        eval_history.append(max(-10, min(10, curr_cp_white / 100)))

        opp_reply_san = None
        if info[0].get("pv"):
            try:
                opp_reply_san = board.san(info[0]["pv"][0])
            except Exception:
                opp_reply_san = None

        if mover == chess.WHITE:
            prev_cp, curr_cp, second_cp = prev_cp_white, curr_cp_white, second_cp_white
        else:
            prev_cp, curr_cp, second_cp = -prev_cp_white, -curr_cp_white, -second_cp_white

        is_only_move = (cp_to_wp(prev_cp) - cp_to_wp(second_cp)) >= 0.20
        book_ok, eco_ply, name_ply = is_book_move(uci_history, ply)
        is_book = book_ok and abs(curr_cp) < 80 and not is_sac

        eco, opening_name = lookup_opening(uci_history)
        if eco and not metadata["ECO"]:
            metadata["ECO"] = eco
        if opening_name:
            metadata["Opening"] = opening_name

        phase = _game_phase(board, ply)
        eval_swing = abs((curr_cp - prev_cp) / 100)

        base_class = classify_move(prev_cp, curr_cp, is_only_move, is_sac, is_book, is_mate_delivered)
        is_miss = is_miss_move(board_before, move, best_move, prev_cp, curr_cp, base_class)
        classification = classify_move(prev_cp, curr_cp, is_only_move, is_sac, is_book,
                                       is_mate_delivered, is_miss=is_miss)

        cp_loss = min(1000, max(0, prev_cp - curr_cp))
        total_cp_loss[mover] += cp_loss
        counted[mover] += 1

        facts, prompt_str = extract_facts(
            board_before, move, best_move, prev_cp, curr_cp,
            classification, opp_reply_san, opening_name, phase)

        entry = {
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
            "best_line": best_line,
            "best_uci": best_move.uci() if best_move else None,
            "eval_swing": eval_swing,
            "phase": phase,
        }
        move_data.append(entry)

        yield "progress", {"ply": ply + 1, "total": total_moves, "move": entry}

        prev_info = info
        prev_cp_white = curr_cp_white
        ply += 1

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
    critical = _critical_moments(move_data)

    yield "complete", {
        "move_data": move_data,
        "stats": summary_stats,
        "meta": metadata,
        "hist": eval_history,
        "critical_moments": critical,
    }


def analyze_game(pgn_str, engine, depth=18):
    result = None
    for event_type, payload in analyze_game_streaming(pgn_str, engine, depth):
        if event_type == "complete":
            result = payload
    if result is None:
        raise ValueError("Analysis produced no result")
    return (result["move_data"], result["stats"], result["meta"],
            result["hist"], result["critical_moments"])


def analyse_fen(fen, engine, depth=18, multipv=3):
    board = chess.Board(fen)
    limit = chess.engine.Limit(depth=depth, time=ENGINE_TIME_LIMIT_SECONDS)
    infos = engine.analyse(board, limit, multipv=multipv)

    lines = []
    for info in infos:
        pov = info["score"].white()
        pv = info.get("pv", [])
        san_line = _pv_to_san(board, pv)
        lines.append({
            "eval": _eval_str(pov),
            "eval_cp_white": pov.score(mate_score=10000),
            "first_uci": pv[0].uci() if pv else None,
            "san_line": san_line,
        })
    return lines

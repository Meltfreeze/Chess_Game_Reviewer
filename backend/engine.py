"""
engine.py — All chess analysis. Stockfish is the ONLY source of chess truth.
"""

import io
import math
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
BRILLIANT_PIECES = {chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN}
BRILLIANT_MIN_SACRIFICE = 2
BRILLIANT_MIN_WIN_PROBABILITY = 0.20
BRILLIANT_VERIFICATION_TOLERANCE = 0.02


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
    """Return whether a move passes the cheap, structural sacrifice gate."""
    return _sacrifice_candidate(board, move)["candidate"]


def cp_to_wp(cp):
    cp = max(-10000, min(10000, cp))
    return 1 / (1 + 10 ** (-cp / 400))


def _win_percent(cp):
    """Win expectancy 0-100 for the side that just moved.

    Kept separate from cp_to_wp on purpose: the accuracy curve below is
    calibrated against this sigmoid, while cp_to_wp feeds the classification
    thresholds and must not shift.
    """
    cp = max(-10000, min(10000, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def _move_accuracy(win_before, win_after):
    """Accuracy 0-100 for one move, from how much win expectancy it gave up."""
    drop = max(0.0, win_before - win_after)
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * drop) - 3.1669))


def _game_accuracy(per_move, win_seq):
    """Collapse per-move accuracies into one 0-100 figure for a player.

    Mean of a volatility-weighted mean and a harmonic mean: the weighting keeps
    quiet positions from drowning out sharp ones, and the harmonic mean stops a
    handful of terrible moves from being averaged away by many easy ones.
    """
    if not per_move:
        return 0.0
    window = max(2, min(8, len(per_move) // 10))
    weights = []
    for i in range(len(per_move)):
        seg = win_seq[max(0, i - window + 1):i + 1] or [50.0]
        mean = sum(seg) / len(seg)
        stdev = (sum((x - mean) ** 2 for x in seg) / len(seg)) ** 0.5
        weights.append(max(0.5, stdev))
    weighted = sum(a * w for a, w in zip(per_move, weights)) / sum(weights)
    harmonic = len(per_move) / sum(1.0 / max(a, 1.0) for a in per_move)
    return round((weighted + harmonic) / 2, 1)


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


def is_unique_best(best_wp, second_best_wp):
    """Return whether the root best move is meaningfully unique.

    The absolute branch catches large practical swings around equality. The
    relative branch also catches defensive resources in already-bad positions,
    where an absolute 20-point gap may be impossible.
    """
    wp_gap = best_wp - second_best_wp
    return (
        wp_gap >= 0.20
        or (wp_gap >= 0.05 and second_best_wp <= best_wp * 0.50)
    )


def _piece_is_hanging(board, square, color):
    piece = board.piece_at(square)
    if not piece or piece.color != color or piece.piece_type == chess.KING:
        return False

    capture_board = board
    if board.turn == color:
        capture_board = board.copy(stack=False)
        capture_board.turn = not color

    for attacker_square in capture_board.attackers(not color, square):
        attacker = capture_board.piece_at(attacker_square)
        promotions = [None]
        if (attacker and attacker.piece_type == chess.PAWN
                and chess.square_rank(square) == BACK_RANK[attacker.color]):
            promotions = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
        for promotion in promotions:
            capture = chess.Move(attacker_square, square, promotion=promotion)
            if (capture_board.is_legal(capture)
                    and static_exchange_eval(capture_board, capture) > 0):
                return True
    return False


def _material_balance(board, color):
    return _material_count(board, color) - _material_count(board, not color)


def _captures_offered_piece(board_after, offered_square):
    return [
        move
        for move in board_after.legal_moves
        if board_after.is_capture(move) and move.to_square == offered_square
    ]


def _sacrifice_candidate(position, move):
    evidence = {
        "candidate": False,
        "verified": False,
        "piece": None,
        "sacrifice_cost": 0,
        "accepted_in_main_pv": False,
        "verified_by_forced_capture": False,
        "maximum_material_deficit": 0,
        "capture_wp": None,
        "reason": None,
    }

    if move not in position.legal_moves:
        evidence["reason"] = "illegal_move"
        return evidence

    mover = position.turn
    piece = position.piece_at(move.from_square)
    if not piece or piece.piece_type not in BRILLIANT_PIECES:
        evidence["reason"] = "ineligible_piece"
        return evidence
    evidence["piece"] = NAMES[piece.piece_type]

    if _piece_is_hanging(position, move.from_square, mover):
        evidence["reason"] = "piece_already_hanging"
        return evidence

    sacrifice_cost = -static_exchange_eval(position, move)
    evidence["sacrifice_cost"] = sacrifice_cost
    if sacrifice_cost < BRILLIANT_MIN_SACRIFICE:
        evidence["reason"] = "insufficient_material_investment"
        return evidence

    after = position.copy(stack=False)
    after.push(move)
    if not _captures_offered_piece(after, move.to_square):
        evidence["reason"] = "offered_piece_not_legally_capturable"
        return evidence

    evidence["candidate"] = True
    return evidence


def _maximum_material_deficit(position, move, continuation):
    mover = position.turn
    baseline = _material_balance(position, mover)
    scratch = position.copy(stack=False)
    scratch.push(move)
    maximum = max(0, baseline - _material_balance(scratch, mover))

    for future_move in continuation:
        if future_move not in scratch.legal_moves:
            break
        scratch.push(future_move)
        maximum = max(maximum, baseline - _material_balance(scratch, mover))
    return maximum


def _score_mover_cp(info, mover):
    white_cp = _score_white_cp(info)
    return white_cp if mover == chess.WHITE else -white_cp


def verify_sacrifice(position, move, post_move_info, engine, limit, best_wp):
    """Verify material investment through Stockfish's future continuations.

    The normal post-move PV is free because the analysis pipeline already paid
    for it. When Stockfish declines the offer, one same-depth search restricted
    to legal captures checks the counterfactual acceptance line.
    """
    evidence = _sacrifice_candidate(position, move)
    if not evidence["candidate"]:
        return evidence

    mover = position.turn
    after = position.copy(stack=False)
    after.push(move)
    capture_moves = _captures_offered_piece(after, move.to_square)
    main_pv = post_move_info[0].get("pv", []) if post_move_info else []

    if main_pv and main_pv[0] in capture_moves:
        evidence["accepted_in_main_pv"] = True
        evidence["maximum_material_deficit"] = _maximum_material_deficit(
            position, move, main_pv
        )
        evidence["verified"] = (
            evidence["maximum_material_deficit"] >= BRILLIANT_MIN_SACRIFICE
        )
        evidence["reason"] = None if evidence["verified"] else "no_material_deficit"
        return evidence

    forced_result = engine.analyse(
        after,
        limit,
        multipv=1,
        root_moves=capture_moves,
    )
    forced_info = forced_result[0] if isinstance(forced_result, list) else forced_result
    forced_pv = forced_info.get("pv", [])
    if not forced_pv or forced_pv[0] not in capture_moves:
        evidence["reason"] = "forced_capture_line_unavailable"
        return evidence

    evidence["maximum_material_deficit"] = _maximum_material_deficit(
        position, move, forced_pv
    )
    evidence["capture_wp"] = cp_to_wp(_score_mover_cp(forced_info, mover))
    evidence["verified_by_forced_capture"] = True
    evidence["verified"] = (
        evidence["maximum_material_deficit"] >= BRILLIANT_MIN_SACRIFICE
        and evidence["capture_wp"] >= best_wp - BRILLIANT_VERIFICATION_TOLERANCE
    )
    if evidence["verified"]:
        evidence["reason"] = None
    elif evidence["maximum_material_deficit"] < BRILLIANT_MIN_SACRIFICE:
        evidence["reason"] = "no_material_deficit"
    else:
        evidence["reason"] = "capture_refutes_sacrifice"
    return evidence


def is_trivially_obvious_brilliant(move, position, legal_move_count,
                                    is_mate=False, previous_move=None,
                                    previous_move_was_capture=False):
    if legal_move_count <= 1 or is_mate or move.promotion is not None:
        return True
    if (previous_move_was_capture and previous_move
            and position.is_capture(move)
            and move.to_square == previous_move.to_square):
        return True

    captured = position.piece_at(move.to_square) if position.is_capture(move) else None
    return bool(
        captured
        and captured.piece_type in (chess.ROOK, chess.QUEEN)
        and not position.attackers(captured.color, move.to_square)
    )


def is_brilliant(played_move, best_move, best_wp, legal_move_count, position,
                 sacrifice_evidence, is_book=False, is_mate=False,
                 previous_move=None, previous_move_was_capture=False):
    return (
        played_move == best_move
        and best_wp > BRILLIANT_MIN_WIN_PROBABILITY
        and legal_move_count > 1
        and sacrifice_evidence["verified"]
        and not is_book
        and not is_mate
        and not is_trivially_obvious_brilliant(
            played_move,
            position,
            legal_move_count,
            is_mate=is_mate,
            previous_move=previous_move,
            previous_move_was_capture=previous_move_was_capture,
        )
    )


def evaluate_brilliant(position, played_move, best_move, best_wp,
                       legal_move_count, is_book, is_mate, post_move_info,
                       engine, limit, previous_move=None,
                       previous_move_was_capture=False):
    """Return the Brilliant decision and its verified sacrifice evidence."""
    evidence = _sacrifice_candidate(position, played_move)
    if not evidence["candidate"]:
        return False, evidence
    if played_move != best_move:
        evidence["reason"] = "not_engine_best"
        return False, evidence
    if best_wp <= BRILLIANT_MIN_WIN_PROBABILITY:
        evidence["reason"] = "position_not_viable"
        return False, evidence
    if is_book:
        evidence["reason"] = "book_move"
        return False, evidence
    if is_trivially_obvious_brilliant(
        played_move,
        position,
        legal_move_count,
        is_mate=is_mate,
        previous_move=previous_move,
        previous_move_was_capture=previous_move_was_capture,
    ):
        evidence["reason"] = "trivially_obvious"
        return False, evidence

    evidence = verify_sacrifice(
        position,
        played_move,
        post_move_info,
        engine,
        limit,
        best_wp,
    )
    return is_brilliant(
        played_move,
        best_move,
        best_wp,
        legal_move_count,
        position,
        evidence,
        is_book=is_book,
        is_mate=is_mate,
        previous_move=previous_move,
        previous_move_was_capture=previous_move_was_capture,
    ), evidence


def _move_is_safe(board, move):
    mover = board.turn
    after = board.copy(stack=False)
    after.push(move)
    return not _piece_is_hanging(after, move.to_square, mover)


def _is_only_unattacked_escape(position, move):
    """Return whether an attacked non-king has exactly one safe destination."""
    piece = position.piece_at(move.from_square)
    if (not piece or piece.color != position.turn
            or piece.piece_type == chess.KING):
        return False

    opponent = not piece.color
    if not position.is_attacked_by(opponent, move.from_square):
        return False

    safe_destinations = set()
    for candidate in position.legal_moves:
        if candidate.from_square != move.from_square:
            continue
        after = position.copy(stack=False)
        after.push(candidate)
        if not after.is_attacked_by(opponent, candidate.to_square):
            safe_destinations.add(candidate.to_square)
            if len(safe_destinations) > 1:
                return False

    return safe_destinations == {move.to_square}


def is_trivially_obvious(move, position, legal_move_count=None,
                         previous_move=None, previous_move_was_capture=False):
    """Identify only the narrow, deterministic set of obvious moves.

    Check evasions, king moves, captures, defensive moves, and checking moves
    are deliberately not enough on their own. Previous-move context is
    optional so arbitrary-FEN callers can conservatively skip recapture
    detection when they cannot prove that the prior move was a capture.
    """
    if legal_move_count is None:
        legal_move_count = position.legal_moves.count()
    if legal_move_count <= 1:
        return True

    safe = _move_is_safe(position, move)
    is_capture = position.is_capture(move)

    if (safe and is_capture and previous_move_was_capture and previous_move
            and move.to_square == previous_move.to_square):
        return True

    captured = position.piece_at(move.to_square) if is_capture else None
    if (safe and captured and captured.piece_type in (chess.ROOK, chess.QUEEN)
            and not position.attackers(captured.color, move.to_square)):
        return True

    if safe and move.promotion == chess.QUEEN:
        return True

    if _is_only_unattacked_escape(position, move):
        return True

    return False


def is_great(played_move, best_move, best_wp, second_best_wp,
             legal_move_count, position, is_book=False, is_mate=False,
             is_brilliant=False, previous_move=None,
             previous_move_was_capture=False):
    return (
        played_move == best_move
        and is_unique_best(best_wp, second_best_wp)
        and legal_move_count > 1
        and not is_trivially_obvious(
            played_move,
            position,
            legal_move_count=legal_move_count,
            previous_move=previous_move,
            previous_move_was_capture=previous_move_was_capture,
        )
        and not is_book
        and not is_mate
        and not is_brilliant
    )


def classify_move(prev_cp, curr_cp, is_great_move, is_brilliant_move, is_book,
                  is_mate=False, is_miss=False):
    """Label one move, ranking the short-circuits before the eval ladder.

    Mate ends the game, so it outranks everything. A book move is established
    theory and is not graded at all -- including not being second-guessed as a
    Miss, which would otherwise read as "you missed a tactic" on known opening
    moves.
    """
    if is_mate:
        return "Best"
    if is_book:
        return "Book"
    wp_loss = cp_to_wp(prev_cp) - cp_to_wp(curr_cp)

    if wp_loss >= 0.20:
        return "Blunder"
    if wp_loss >= 0.12:
        return "Mistake"
    if wp_loss >= 0.06:
        return "Inaccuracy"
    if is_miss:
        return "Miss"
    if is_brilliant_move:
        return "Brilliant"
    if is_great_move:
        return "Great"
    if wp_loss >= 0.03:
        return "Good"
    if wp_loss >= 0.02:
        return "Excellent"
    return "Best"


def _previous_capture_context(board):
    """Return exact previous-move capture context when board history exists."""
    if not board.move_stack:
        return None, False
    previous_move = board.peek()
    before_previous = board.copy(stack=True)
    before_previous.pop()
    return previous_move, before_previous.is_capture(previous_move)


def _history_capture_context(position, uci_history):
    """Replay standard-start history, failing closed when it does not match."""
    if not uci_history:
        return None, False
    replay = chess.Board()
    try:
        for uci in uci_history:
            move = chess.Move.from_uci(uci)
            if move not in replay.legal_moves:
                return None, False
            replay.push(move)
    except (TypeError, ValueError):
        return None, False

    if replay.fen() != position.fen():
        return None, False
    return _previous_capture_context(replay)


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
            out.append((NAMES[piece.piece_type], chess.square_name(sq), best_gain,
                        board.is_pinned(color, sq)))
    out.sort(key=lambda x: -x[2])
    return out


def _format_hanging(hanging):
    return [
        f"{name} on {square}" + (" (pinned)" if pinned else "")
        for name, square, _gain, pinned in hanging
    ]


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


def _multipv_signals(board_before, prev_info, board_after, info):
    """Reuse the two existing searches to expose concrete continuations.

    ``info`` is the search after the played move, so its first PV starts with
    the opponent's best reply. ``prev_info[1]`` is Stockfish's runner-up before
    the move. No search is performed here; this helper only preserves and
    checks data the caller already paid for.
    """
    forcing_line = []
    if info and info[0].get("pv"):
        line = _pv_to_san(board_after, info[0]["pv"], max_plies=4)
        if len(line) >= 2:
            forcing_line = line

    runner_up = None
    runner_up_hanging = []
    if len(prev_info) > 1 and prev_info[1].get("pv"):
        move = prev_info[1]["pv"][0]
        if move in board_before.legal_moves:
            runner_up = board_before.san(move)
            after_runner_up = board_before.copy(stack=False)
            after_runner_up.push(move)
            runner_up_hanging = _format_hanging(
                _hanging_pieces(after_runner_up, board_before.turn)
            )[:2]

    return {
        "forcing_line": forcing_line,
        "runner_up": runner_up,
        "runner_up_hanging": runner_up_hanging,
    }


def extract_facts(board_before, move, best_move, eval_before_cp, eval_after_cp,
                  classification, opp_reply_san=None, opening_name=None, phase=None,
                  is_sacrifice=False, best_line=None, forcing_line=None,
                  runner_up=None, runner_up_hanging=None):
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
        "is_sacrifice": is_sacrifice,
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
    hanging = [item for item in hanging_raw if mistake_class or item[2] >= 3]
    facts["hanging"] = _format_hanging(hanging[:2])

    facts["refutation"] = None
    if classification in ("Blunder", "Mistake", "Inaccuracy") and opp_reply_san:
        facts["refutation"] = opp_reply_san

    facts["missed_best"] = facts["best"]

    if (classification in ("Blunder", "Mistake", "Inaccuracy", "Miss")
            and facts["best"] and best_line and len(best_line) >= 2):
        facts["best_line"] = best_line[:4]

    if classification in ("Blunder", "Mistake") and forcing_line:
        facts["forcing_line"] = forcing_line[:4]

    if classification == "Great" and runner_up:
        facts["runner_up"] = runner_up
        facts["runner_up_hanging"] = (runner_up_hanging or [])[:2]
        facts["runner_up_fails"] = bool(facts["runner_up_hanging"])

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
    if facts["is_sacrifice"]:
        bits.append("verified sacrifice")
    if facts.get("missed_capture"):
        bits.append(f'missed capture {facts["missed_capture"]}')
    if facts["best"]:
        bits.append(f'engine preferred {facts["best"]}')
    if facts.get("best_line"):
        bits.append("engine continuation: " + " ".join(facts["best_line"]))
    if facts.get("material_lost"):
        bits.append(f'lost {facts["material_lost"]} material value')
    if facts.get("king_in_check"):
        bits.append("king exposed to check")
    if facts["hanging"]:
        bits.append("leaves hanging: " + ", ".join(facts["hanging"]))
    if facts["refutation"]:
        bits.append(f'opponent can reply {facts["refutation"]}')
    if facts.get("forcing_line"):
        bits.append("forcing continuation: " + " ".join(facts["forcing_line"]))
    if facts.get("runner_up"):
        bits.append(f'runner-up was {facts["runner_up"]}')
    if facts.get("runner_up_hanging"):
        bits.append("runner-up leaves hanging: " + ", ".join(facts["runner_up_hanging"]))
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
    move_accuracies = {chess.WHITE: [], chess.BLACK: []}
    win_after_seq = {chess.WHITE: [], chess.BLACK: []}
    uci_history = []
    ply = 0

    total_moves = sum(1 for _ in game.mainline())

    for game_node in game.mainline():
        move = game_node.move
        mover = board.turn
        previous_move, previous_move_was_capture = _previous_capture_context(board)
        board_before = board.copy(stack=False)
        best_move = prev_info[0]["pv"][0] if prev_info[0].get("pv") else None
        best_line = _pv_to_san(board_before, prev_info[0].get("pv", []))
        san = board.san(move)

        stays_in_book = is_book_move(uci_history, move.uci())
        second_cp_white = (_score_white_cp(prev_info[1])
                           if len(prev_info) > 1 else prev_cp_white)

        board.push(move)
        uci_history.append(move.uci())
        is_mate_delivered = board.is_checkmate()

        info = engine.analyse(board, limit, multipv=2)
        curr_cp_white = _score_white_cp(info[0])
        pov = info[0]["score"].white()
        eval_history.append(max(-10, min(10, curr_cp_white / 100)))
        multipv_signals = _multipv_signals(board_before, prev_info, board, info)

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

        best_wp = cp_to_wp(prev_cp)
        second_best_wp = cp_to_wp(second_cp)
        legal_move_count = board_before.legal_moves.count()
        is_book = stays_in_book and abs(curr_cp) < 80
        brilliant_candidate, sacrifice_evidence = evaluate_brilliant(
            board_before,
            move,
            best_move,
            best_wp,
            legal_move_count,
            is_book,
            is_mate_delivered,
            info,
            engine,
            limit,
            previous_move=previous_move,
            previous_move_was_capture=previous_move_was_capture,
        )
        great_candidate = is_great(
            move,
            best_move,
            best_wp,
            second_best_wp,
            legal_move_count,
            board_before,
            is_book=is_book,
            is_mate=is_mate_delivered,
            is_brilliant=brilliant_candidate,
            previous_move=previous_move,
            previous_move_was_capture=previous_move_was_capture,
        )

        eco, opening_name = lookup_opening(uci_history)
        if opening_name:
            # Both fields move together. Setting ECO once while the name kept
            # refining every ply paired a first-move code with a deep-line name.
            metadata["ECO"] = eco
            metadata["Opening"] = opening_name

        phase = _game_phase(board, ply)
        eval_swing = abs((curr_cp - prev_cp) / 100)

        base_class = classify_move(
            prev_cp,
            curr_cp,
            great_candidate,
            brilliant_candidate,
            is_book,
            is_mate_delivered,
        )
        is_miss = is_miss_move(board_before, move, best_move, prev_cp, curr_cp, base_class)
        classification = classify_move(
            prev_cp,
            curr_cp,
            great_candidate,
            brilliant_candidate,
            is_book,
            is_mate_delivered,
            is_miss=is_miss,
        )

        cp_loss = min(1000, max(0, prev_cp - curr_cp))
        total_cp_loss[mover] += cp_loss
        counted[mover] += 1

        win_before, win_after = _win_percent(prev_cp), _win_percent(curr_cp)
        move_accuracies[mover].append(_move_accuracy(win_before, win_after))
        win_after_seq[mover].append(win_after)

        facts, prompt_str = extract_facts(
            board_before, move, best_move, prev_cp, curr_cp,
            classification, opp_reply_san, opening_name, phase,
            is_sacrifice=sacrifice_evidence["verified"],
            best_line=best_line,
            **multipv_signals)

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
            "best_move": best_move.uci() if best_move else None,
            "played_move": move.uci(),
            "best_wp": best_wp,
            "second_best_wp": second_best_wp,
            "legal_move_count": legal_move_count,
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
        "White": {
            "rating": w_rating,
            "acpl": w_acpl,
            "accuracy": _game_accuracy(move_accuracies[chess.WHITE],
                                       win_after_seq[chess.WHITE]),
        },
        "Black": {
            "rating": b_rating,
            "acpl": b_acpl,
            "accuracy": _game_accuracy(move_accuracies[chess.BLACK],
                                       win_after_seq[chess.BLACK]),
        },
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


def analyze_move(fen, uci, engine, depth=18, ply=0, uci_history=None):
    """Review a single move played from an arbitrary position.

    Produces the same entry shape as analyze_game_streaming, so a move explored
    off the reviewed game runs through the identical classification and fact
    pipeline as a real one. uci_history is the UCI path from the starting
    position up to (not including) this move; pass None to skip book/opening
    detection when the path is unknown.
    """
    board_before = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    if move not in board_before.legal_moves:
        raise ValueError(f"{uci} is not legal in this position")

    limit = chess.engine.Limit(depth=depth, time=ENGINE_TIME_LIMIT_SECONDS)
    prev_info = engine.analyse(board_before, limit, multipv=2)
    prev_cp_white = _score_white_cp(prev_info[0])
    second_cp_white = (_score_white_cp(prev_info[1])
                       if len(prev_info) > 1 else prev_cp_white)
    best_move = prev_info[0]["pv"][0] if prev_info[0].get("pv") else None
    best_line = _pv_to_san(board_before, prev_info[0].get("pv", []))

    mover = board_before.turn
    san = board_before.san(move)

    board = board_before.copy(stack=False)
    board.push(move)
    is_mate_delivered = board.is_checkmate()

    info = engine.analyse(board, limit, multipv=2)
    curr_cp_white = _score_white_cp(info[0])
    pov = info[0]["score"].white()
    multipv_signals = _multipv_signals(board_before, prev_info, board, info)

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

    best_wp = cp_to_wp(prev_cp)
    second_best_wp = cp_to_wp(second_cp)
    legal_move_count = board_before.legal_moves.count()
    previous_move, previous_move_was_capture = _history_capture_context(
        board_before, uci_history
    )

    is_book = False
    opening_name = None
    if uci_history is not None:
        # Same convention as analyze_game_streaming: both the book test and the
        # opening name see the line *including* the move being judged, so the
        # same move gets the same classification either way.
        is_book = is_book_move(uci_history, move.uci()) and abs(curr_cp) < 80
        _, opening_name = lookup_opening([*uci_history, move.uci()])

    brilliant_candidate, sacrifice_evidence = evaluate_brilliant(
        board_before,
        move,
        best_move,
        best_wp,
        legal_move_count,
        is_book,
        is_mate_delivered,
        info,
        engine,
        limit,
        previous_move=previous_move,
        previous_move_was_capture=previous_move_was_capture,
    )
    great_candidate = is_great(
        move,
        best_move,
        best_wp,
        second_best_wp,
        legal_move_count,
        board_before,
        is_book=is_book,
        is_mate=is_mate_delivered,
        is_brilliant=brilliant_candidate,
        previous_move=previous_move,
        previous_move_was_capture=previous_move_was_capture,
    )

    phase = _game_phase(board, ply)
    base_class = classify_move(
        prev_cp,
        curr_cp,
        great_candidate,
        brilliant_candidate,
        is_book,
        is_mate_delivered,
    )
    is_miss = is_miss_move(board_before, move, best_move, prev_cp, curr_cp, base_class)
    classification = classify_move(
        prev_cp,
        curr_cp,
        great_candidate,
        brilliant_candidate,
        is_book,
        is_mate_delivered,
        is_miss=is_miss,
    )

    facts, prompt_str = extract_facts(
        board_before, move, best_move, prev_cp, curr_cp,
        classification, opp_reply_san, opening_name, phase,
        is_sacrifice=sacrifice_evidence["verified"],
        best_line=best_line,
        **multipv_signals)

    return {
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
        "cp_loss": min(1000, max(0, prev_cp - curr_cp)),
        "best_line": best_line,
        "best_uci": best_move.uci() if best_move else None,
        "best_move": best_move.uci() if best_move else None,
        "played_move": move.uci(),
        "best_wp": best_wp,
        "second_best_wp": second_best_wp,
        "legal_move_count": legal_move_count,
        "eval_swing": abs((curr_cp - prev_cp) / 100),
        "phase": phase,
    }


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

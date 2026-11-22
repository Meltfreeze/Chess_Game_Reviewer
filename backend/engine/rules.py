"""Chess-rule helpers used to classify reviewed moves."""

import chess

from .scoring import _score_white_cp, cp_to_wp


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
        "capture_pv": [],
        "capture_cp": None,
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
        evidence["capture_pv"] = main_pv
        if post_move_info[0].get("score") is not None:
            evidence["capture_cp"] = _score_mover_cp(post_move_info[0], mover)
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
    evidence["capture_cp"] = _score_mover_cp(forced_info, mover)
    evidence["capture_pv"] = forced_pv
    evidence["capture_wp"] = cp_to_wp(evidence["capture_cp"])
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

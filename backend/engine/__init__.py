"""Public chess-analysis façade and adaptive search orchestration."""

import io

import chess
import chess.engine
import chess.pgn

from backend.config import ENGINE_TIME_LIMIT_SECONDS, FAST_ANALYSIS_DEPTH, FAST_ANALYSIS_TIME_SECONDS
from .facts import (
    _capture_consequence,
    _critical_moments,
    _format_hanging,
    _hanging_pieces,
    _history_capture_context,
    _multipv_signals,
    _previous_capture_context,
    _pv_to_san,
    extract_facts,
)
from .review import build_move_entry as _build_move_entry
from .rules import (
    BACK_RANK, BRILLIANT_MIN_SACRIFICE, BRILLIANT_MIN_WIN_PROBABILITY,
    BRILLIANT_PIECES, BRILLIANT_VERIFICATION_TOLERANCE, CRITICAL_CLASSES,
    NAMES, NOTABLE, VALUES, _captures_offered_piece, _game_phase,
    _is_only_unattacked_escape, _least_valuable_attacker, _material_balance,
    _material_count, _maximum_material_deficit, _move_is_safe,
    _piece_is_hanging, _promoted_type, _sacrifice_candidate, _score_mover_cp,
    classify_move, evaluate_brilliant, is_brilliant, is_great, is_miss_move,
    is_sacrifice, is_trivially_obvious, is_trivially_obvious_brilliant,
    is_unique_best, static_exchange_eval, verify_sacrifice,
)
from .scoring import _eval_str, _game_accuracy, _move_accuracy, _score_white_cp, _win_percent, cp_to_wp
from backend.openings import is_book_move, lookup_opening


def _review_limits(depth):
    deep = chess.engine.Limit(depth=depth, time=ENGINE_TIME_LIMIT_SECONDS)
    if depth <= FAST_ANALYSIS_DEPTH:
        return deep, deep
    fast = chess.engine.Limit(depth=FAST_ANALYSIS_DEPTH, time=FAST_ANALYSIS_TIME_SECONDS)
    return fast, deep


def _needs_deep_from_position(before, move, before_info):
    """Recognize deep-review candidates before searching the next position."""
    mover = before.turn
    best_line = before_info[0].get("pv", [])
    best_move = best_line[0] if best_line else None
    if (before.is_capture(move) or before.gives_check(move)
            or before.is_check() or move.promotion):
        return True
    if (best_move == move and before.legal_moves.count() > 1
            and not is_trivially_obvious(move, before)):
        return True
    if len(before_info) > 1:
        before_cp = _score_mover_cp(before_info[0], mover)
        second_cp = _score_mover_cp(before_info[1], mover)
        best_wp, second_wp = cp_to_wp(before_cp), cp_to_wp(second_cp)
        if is_unique_best(best_wp, second_wp):
            return True
        runner_up = before_info[1].get("pv", [])
        if runner_up and runner_up[0] == move:
            return True
    piece = before.piece_at(move.from_square)
    return bool(piece and piece.piece_type in BRILLIANT_PIECES
                and _sacrifice_candidate(before, move)["candidate"])


def _needs_deep_review(before, move, before_info, after_info, stays_in_book=False):
    """Use the fast reply search to catch evaluation swings and missed moves."""
    mover = before.turn
    after_cp = _score_mover_cp(after_info[0], mover)
    if stays_in_book and abs(after_cp) < 80:
        return False
    if _needs_deep_from_position(before, move, before_info):
        return True
    before_cp = _score_mover_cp(before_info[0], mover)
    loss = cp_to_wp(before_cp) - cp_to_wp(after_cp)
    best_line = before_info[0].get("pv", [])
    best_move = best_line[0] if best_line else None
    return abs(loss) >= 0.03 or (best_move != move and loss >= 0.015)


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
    fast_limit, deep_limit = _review_limits(depth)
    prev_info = engine.analyse(board, fast_limit, multipv=2)
    prev_is_deep = fast_limit is deep_limit

    move_data = []
    eval_history = [0.0]
    total_cp_loss = {chess.WHITE: 0, chess.BLACK: 0}
    counted = {chess.WHITE: 0, chess.BLACK: 0}
    move_accuracies = {chess.WHITE: [], chess.BLACK: []}
    win_after_seq = {chess.WHITE: [], chess.BLACK: []}
    uci_history = []
    ply = 0

    total_moves = sum(1 for _ in game.mainline())

    def finish_move(context, final_info):
        nonlocal ply
        before, after, played, before_info, opening_name, history, book = context
        mover = before.turn
        before_cp_white = _score_white_cp(before_info[0])
        after_cp_white = _score_white_cp(final_info[0])
        mover_cp = after_cp_white if mover == chess.WHITE else -after_cp_white
        previous_move, previous_was_capture = _previous_capture_context(history)
        entry = _build_move_entry(
            before, after, played, before_info, final_info,
            before_cp_white, after_cp_white, book and abs(mover_cp) < 80,
            opening_name, previous_move, previous_was_capture,
            engine, deep_limit, ply,
        )
        total_cp_loss[mover] += entry["cp_loss"]
        counted[mover] += 1
        before_cp = before_cp_white if mover == chess.WHITE else -before_cp_white
        win_before, win_after = _win_percent(before_cp), _win_percent(mover_cp)
        move_accuracies[mover].append(_move_accuracy(win_before, win_after))
        win_after_seq[mover].append(win_after)
        eval_history.append(max(-10, min(10, after_cp_white / 100)))
        move_data.append(entry)
        ply += 1
        return entry

    # Hold one move until the next one is inspected: its destination may need
    # a deeper search when it turns out to be the next move's starting square.
    pending = None
    for game_node in game.mainline():
        move = game_node.move
        history = board.copy(stack=True)
        board_before = board.copy(stack=False)
        stays_in_book = is_book_move(uci_history, move.uci())

        board.push(move)
        uci_history.append(move.uci())
        deep_now = (fast_limit is not deep_limit and not stays_in_book
                    and _needs_deep_from_position(board_before, move, prev_info))
        if deep_now:
            if not prev_is_deep:
                prev_info = engine.analyse(board_before, deep_limit, multipv=2)
                prev_is_deep = True
            info = engine.analyse(board, deep_limit, multipv=2)
            info_is_deep = True
        else:
            info = engine.analyse(board, fast_limit, multipv=2)
            if fast_limit is not deep_limit and _needs_deep_review(
                    board_before, move, prev_info, info,
                    stays_in_book=stays_in_book):
                if not prev_is_deep:
                    prev_info = engine.analyse(board_before, deep_limit, multipv=2)
                    prev_is_deep = True
                info = engine.analyse(board, deep_limit, multipv=2)
                info_is_deep = True
            else:
                info_is_deep = fast_limit is deep_limit

        if pending is not None:
            entry = finish_move(pending, prev_info)
            yield "progress", {"ply": entry["ply"] + 1,
                               "total": total_moves, "move": entry}

        eco, opening_name = lookup_opening(uci_history)
        if opening_name:
            metadata["ECO"] = eco
            metadata["Opening"] = opening_name

        pending = (board_before, board.copy(stack=False), move, prev_info,
                   opening_name, history, stays_in_book)
        prev_info = info
        prev_is_deep = info_is_deep

    if pending is not None:
        entry = finish_move(pending, prev_info)
        yield "progress", {"ply": entry["ply"] + 1,
                           "total": total_moves, "move": entry}

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
    return (result["move_data"], result["stats"], result["meta"], result["hist"], result["critical_moments"])


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

    fast_limit, deep_limit = _review_limits(depth)
    prev_info = engine.analyse(board_before, fast_limit, multipv=2)

    board = board_before.copy(stack=False)
    board.push(move)

    stays_in_book = (uci_history is not None
                     and is_book_move(uci_history, move.uci()))
    deep_now = (fast_limit is not deep_limit and not stays_in_book
                and _needs_deep_from_position(board_before, move, prev_info))
    if deep_now:
        prev_info = engine.analyse(board_before, deep_limit, multipv=2)
        info = engine.analyse(board, deep_limit, multipv=2)
    else:
        info = engine.analyse(board, fast_limit, multipv=2)
        if fast_limit is not deep_limit and _needs_deep_review(
                board_before, move, prev_info, info,
                stays_in_book=stays_in_book):
            prev_info = engine.analyse(board_before, deep_limit, multipv=2)
            info = engine.analyse(board, deep_limit, multipv=2)
    prev_cp_white = _score_white_cp(prev_info[0])
    curr_cp_white = _score_white_cp(info[0])
    previous_move, previous_move_was_capture = _history_capture_context(
        board_before, uci_history
    )

    is_book = False
    opening_name = None
    if uci_history is not None:
        # Same convention as analyze_game_streaming: both the book test and the
        # opening name see the line *including* the move being judged, so the
        # same move gets the same classification either way.
        mover = board_before.turn
        curr_cp = curr_cp_white if mover == chess.WHITE else -curr_cp_white
        is_book = stays_in_book and abs(curr_cp) < 80
        _, opening_name = lookup_opening([*uci_history, move.uci()])

    return _build_move_entry(
        board_before,
        board,
        move,
        prev_info,
        info,
        prev_cp_white,
        curr_cp_white,
        is_book,
        opening_name,
        previous_move,
        previous_move_was_capture,
        engine,
        deep_limit,
        ply,
    )


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

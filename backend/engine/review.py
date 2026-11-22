"""Assembly of one reviewed chess-move response entry."""

import chess

from .facts import (
    _capture_consequence,
    _multipv_signals,
    _pv_to_san,
    extract_facts,
)
from .rules import (
    NOTABLE,
    _game_phase,
    classify_move,
    evaluate_brilliant,
    is_great,
    is_miss_move,
)
from .scoring import _eval_str, _score_white_cp, cp_to_wp


def build_move_entry(board_before, board, move, prev_info, info,
                     prev_cp_white, curr_cp_white, is_book, opening_name,
                     previous_move, previous_move_was_capture, engine, limit,
                     ply):
    """Build one reviewed-move entry from the caller's existing searches."""
    mover = board_before.turn
    san = board_before.san(move)
    best_move = prev_info[0]["pv"][0] if prev_info[0].get("pv") else None
    best_line = _pv_to_san(board_before, prev_info[0].get("pv", []))
    second_cp_white = (_score_white_cp(prev_info[1])
                       if len(prev_info) > 1 else prev_cp_white)
    is_mate_delivered = board.is_checkmate()
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

    cp_loss = min(1000, max(0, prev_cp - curr_cp))
    capture_consequence = None
    if classification in NOTABLE:
        capture_consequence = _capture_consequence(
            board_before,
            board,
            move,
            info,
            engine,
            limit,
            sacrifice_evidence=sacrifice_evidence,
        )
    facts, prompt_str = extract_facts(
        board_before, move, best_move, prev_cp, curr_cp,
        classification, opp_reply_san, opening_name, phase,
        is_sacrifice=sacrifice_evidence["verified"],
        best_line=best_line,
        capture_consequence=capture_consequence,
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
        "cp_loss": cp_loss,
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

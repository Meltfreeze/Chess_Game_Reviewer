"""Position facts and SAN-line formatting for reviewed chess moves."""

import chess

from .rules import (
    CRITICAL_CLASSES,
    NAMES,
    _game_phase,
    _material_balance,
    _material_count,
    static_exchange_eval,
)
from .scoring import _score_white_cp


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


def _capture_consequence(board_before, board_after, move, post_move_info, engine, limit,
                         sacrifice_evidence=None):
    """Return the verified result of recapturing the piece just moved.

    A raw hanging-piece fact only says that a local material exchange looks
    profitable. For a capture, that is not enough to coach the move: the
    captured piece may already have won more material, or Stockfish may find a
    tactical continuation after the recapture. Reuse the normal post-move PV
    when it starts with a profitable recapture; otherwise make one restricted
    search over those recaptures. Classification never depends on this helper.
    """
    if not board_before.is_capture(move):
        return None

    mover = board_before.turn
    landed_piece = board_after.piece_at(move.to_square)
    if not landed_piece or landed_piece.color != mover:
        return None

    recaptures = [
        candidate
        for candidate in board_after.legal_moves
        if (board_after.is_capture(candidate)
            and candidate.to_square == move.to_square
            and static_exchange_eval(board_after, candidate) > 0)
    ]
    if not recaptures:
        return None

    forced_info = None
    forced_cp = None
    pv = post_move_info[0].get("pv", []) if post_move_info else []
    sacrifice_pv = (sacrifice_evidence or {}).get("capture_pv") or []
    if sacrifice_pv and sacrifice_pv[0] in recaptures:
        pv = sacrifice_pv
        forced_cp = sacrifice_evidence.get("capture_cp")
    elif pv and pv[0] in recaptures:
        forced_info = post_move_info[0]
    else:
        forced = engine.analyse(
            board_after,
            limit,
            multipv=1,
            root_moves=recaptures,
        )
        forced_info = forced[0] if isinstance(forced, list) else forced
        pv = forced_info.get("pv", [])

    if not pv or pv[0] not in recaptures:
        return None
    if forced_cp is None and forced_info is None:
        return None

    recapture = pv[0]
    after_recapture = board_after.copy(stack=False)
    after_recapture.push(recapture)
    material_delta = (
        _material_balance(after_recapture, mover)
        - _material_balance(board_before, mover)
    )

    return {
        "piece": f"{NAMES[landed_piece.piece_type]} on {chess.square_name(move.to_square)}",
        "recapture": board_after.san(recapture),
        "line": _pv_to_san(board_after, pv, max_plies=4),
        "material_delta": material_delta,
        "eval_after": round(
            (forced_cp if forced_cp is not None else _score_mover_cp(forced_info, mover))
            / 100,
            1,
        ),
    }


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
                  runner_up=None, runner_up_hanging=None,
                  capture_consequence=None):
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
    if capture_consequence:
        facts["capture_consequence"] = capture_consequence

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
    if facts.get("capture_consequence"):
        consequence = facts["capture_consequence"]
        bits.append(
            "recapture consequence: "
            f"{consequence['recapture']} takes {consequence['piece']}; "
            f"material change {consequence['material_delta']:+}; "
            f"engine line {' '.join(consequence['line'])}; "
            f"mover eval after recapture {consequence['eval_after']:+}"
        )
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


def _score_mover_cp(info, mover):
    white_cp = _score_white_cp(info)
    return white_cp if mover == chess.WHITE else -white_cp


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

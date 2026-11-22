"""Gemini prompt construction and compact verified-fact payloads."""

import hashlib
import json
import re

from backend.engine import NOTABLE

_PIECE_WORDS = {"pawn", "knight", "bishop", "rook", "queen", "king"}
_SQUARE_RE = re.compile(r"\b[a-h][1-8]\b")
_MOVE_NUMBER_RE = re.compile(
    r"\b\d+\.(?:\.\.)?|\b(?:on\s+)?move\s+\d+\b",
    re.IGNORECASE,
)
_SUMMARY_CLASS_PATTERNS = {
    "Blunder": re.compile(r"\bblunders?\b", re.IGNORECASE),
    "Mistake": re.compile(r"\bmistakes?\b", re.IGNORECASE),
    "Inaccuracy": re.compile(r"\binaccurac(?:y|ies)\b", re.IGNORECASE),
    "Miss": re.compile(r"\bmiss(?:es|ed opportunities?)\b", re.IGNORECASE),
    "Brilliant": re.compile(r"\bbrilliant moves?\b|\bbrillianc(?:y|ies)\b", re.IGNORECASE),
    "Great": re.compile(r"\bgreat moves?\b", re.IGNORECASE),
    "Excellent": re.compile(r"\bexcellent moves?\b", re.IGNORECASE),
    "Good": re.compile(r"\bgood moves?\b", re.IGNORECASE),
    "Best": re.compile(r"\bbest moves?\b", re.IGNORECASE),
    "Book": re.compile(r"\bbook moves?\b", re.IGNORECASE),
}
_COUNT_WORDS = {
    "no": 0,
    "zero": 0,
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}
_SUMMARY_INVENTORY_RE = re.compile(
    r"\b(?:no|zero|one|two|three|four|five|\d+)\s+"
    r"(?:book|best|good|excellent|great|brilliant|strong)\s+moves?\b|"
    r"\b(?:no|zero|one|two|three|four|five|\d+)\s+"
    r"(?:blunders?|mistakes?|inaccurac(?:y|ies)|miss(?:es|ed opportunities?))\b",
    re.IGNORECASE,
)
_SUMMARY_NARRATIVE_RE = re.compile(
    r"\b(?:decisive|turning point|allow(?:ed|ing)?|lead(?:ing)?|led|cost|"
    r"miss(?:ed|ing)?|lost|won|convert(?:ed|ing)?|finish(?:ed|ing)?|checkmate|mate)\b",
    re.IGNORECASE,
)
_SUMMARY_TURNING_CLASSES = {
    "Blunder",
    "Mistake",
    "Inaccuracy",
    "Miss",
    "Brilliant",
    "Great",
}
_SUMMARY_NEGATIVE_CLASSES = {"Blunder", "Mistake", "Inaccuracy", "Miss"}
_SUMMARY_CLASS_PRIORITY = {
    "Blunder": 6,
    "Mistake": 5,
    "Miss": 4,
    "Inaccuracy": 3,
    "Brilliant": 2,
    "Great": 1,
}



_SYSTEM = (
    "You are a warm, concise chess coach. You are given engine-VERIFIED facts "
    "about chess moves. Write plain-English commentary using ONLY those facts. "
    "Never invent threats, attacks, piece names, or squares that are not in the "
    "facts; name a move by the exact notation given (e.g. Nf3) rather than a piece "
    "type the facts do not name. Never include move numbers such as '3.', '3...', "
    "or 'move 3'; the SAN alone is sufficient. No jargon dumps. Output strict JSON "
    "only.\n"
    "Blunder/Mistake/Inaccuracy/Miss/Great/Brilliant: say what happened and briefly "
    "why. A label by itself is invalid. Cite the most concrete available verified "
    "fact in this order: a pinned hanging piece; a forcing continuation; a missed "
    "capture; the engine's preferred continuation; the runner-up and why it fails; "
    "a verified sacrifice. The opponent's best reply is also a concrete reason when "
    "no richer continuation is available, including for Inaccuracies. "
    "When facts include a recapture consequence, name both the exposed piece and "
    "the verified recapture, then explain its stated material result or engine "
    "outcome. Never call a piece hanging without reconciling that consequence. "
    "'engine continuation' is "
    "Stockfish's line after its preferred move. 'forcing continuation' starts with "
    "the opponent's best reply. 'runner-up leaves hanging' explains why the Great "
    "move was uniquely necessary. "
    "Max 2 sentences.\n"
    "Good/Best/Excellent/Book: exactly one plain sentence, no reasoning, except that "
    "a Good verified sacrifice may say it was a sacrifice.\n"
    "Never open or pad a comment with the game phase ('in the opening', 'in the "
    "middlegame', 'in the endgame') — mention phase only when it is essential to "
    "the point being made."
)



def _game_key(move_data):
    h = hashlib.sha1()
    for m in move_data:
        h.update(f'{m["uci"]}{m["classification"]}'.encode())
    return h.hexdigest()


def _classification_counts(move_data):
    counts = {"White": {}, "Black": {}}
    for move in move_data:
        turn = move.get("turn")
        classification = move.get("classification")
        if turn not in counts or not isinstance(classification, str):
            continue
        counts[turn][classification] = counts[turn].get(classification, 0) + 1
    return counts


def _summary_context(move_data):
    counts = _classification_counts(move_data)
    opening = next(
        (move.get("facts", {}).get("opening") for move in reversed(move_data)
         if move.get("facts", {}).get("opening")),
        None,
    )
    checkmate_by = None
    checkmate_move = None
    if move_data:
        final_move = move_data[-1]
        final_san = final_move.get("san") or final_move.get("facts", {}).get("played", "")
        if isinstance(final_san, str) and final_san.endswith("#"):
            checkmate_by = final_move.get("turn")
            checkmate_move = _move_prompt_payload(final_move, len(move_data) - 1)
    return {
        "turning_points": _summary_turning_points(move_data),
        "classification_counts": counts,
        "opening": opening,
        "checkmate_by": checkmate_by,
        "checkmate_move": checkmate_move,
    }


def _compact_move_facts(facts):
    """Send only relevant verified facts; validation keeps the full move data."""
    compact = {}
    before = facts.get("eval_before")
    after = facts.get("eval_after")
    if before is not None and after is not None:
        compact["eval"] = [before, after]

    for key in ("hanging", "forcing_line", "missed_capture", "best_line",
                "runner_up", "runner_up_hanging", "refutation", "material_lost"):
        value = facts.get(key)
        if value:
            compact[key] = value

    if facts.get("best") and not facts.get("best_line"):
        compact["best"] = facts["best"]
    if (compact.get("forcing_line") and compact.get("refutation")
            == compact["forcing_line"][0]):
        del compact["refutation"]
    if facts.get("is_sacrifice"):
        compact["sacrifice"] = True
    if facts.get("is_check"):
        compact["gives_check"] = True
    if facts.get("king_in_check"):
        compact["king_in_check"] = True
    if facts.get("capture_consequence"):
        compact["capture_consequence"] = facts["capture_consequence"]
    return compact


def _move_prompt_payload(move, index):
    return {
        "id": index,
        "turn": move.get("turn"),
        "san": move.get("san") or move.get("facts", {}).get("played"),
        "classification": move.get("classification"),
        "facts": _compact_move_facts(move.get("facts") or {}),
    }


def _summary_turning_points(move_data, cap=2):
    candidates = [
        (index, move)
        for index, move in enumerate(move_data)
        if move.get("classification") in _SUMMARY_TURNING_CLASSES
    ]
    ranked = sorted(
        candidates,
        key=lambda item: (
            float(item[1].get("cp_loss") or 0),
            _SUMMARY_CLASS_PRIORITY.get(item[1].get("classification"), 0),
        ),
        reverse=True,
    )[:cap]
    return [
        _move_prompt_payload(move, index)
        for index, move in sorted(ranked, key=lambda item: item[0])
    ]



def _format_summary_move(move):
    return move.get("san") or move.get("facts", {}).get("played") or "the move"


def _select_notable(move_data, cap=24):
    idxs = [i for i, m in enumerate(move_data) if m["classification"] in NOTABLE]
    if len(idxs) > cap:
        idxs = sorted(idxs, key=lambda i: -move_data[i]["cp_loss"])[:cap]
        idxs = sorted(idxs)
    return idxs


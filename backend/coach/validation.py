"""Validation of generated coaching prose against verified engine facts."""

import re

from backend.engine import NOTABLE
from .prompts import (_SUMMARY_CLASS_PATTERNS, _SUMMARY_INVENTORY_RE, _SUMMARY_NARRATIVE_RE, _classification_counts, _format_summary_move, _summary_context, _summary_turning_points)

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



def _nearby_claimed_count(sentence, term_start):
    prefix = sentence[max(0, term_start - 28):term_start]
    matches = re.findall(r"\b(?:no|zero|a|an|one|two|three|four|five|\d+)\b", prefix,
                         re.IGNORECASE)
    if not matches:
        return None
    raw = matches[-1].lower()
    return int(raw) if raw.isdigit() else _COUNT_WORDS[raw]


def _claim_side(sentence, term_start):
    mentions = []
    for match in re.finditer(r"\bwhite\b", sentence, re.IGNORECASE):
        mentions.append((match.start(), "White"))
    for match in re.finditer(r"\bblack\b", sentence, re.IGNORECASE):
        mentions.append((match.start(), "Black"))
    if not mentions:
        return None
    preceding = [mention for mention in mentions if mention[0] <= term_start]
    if preceding:
        return max(preceding, key=lambda item: item[0])[1]
    return min(mentions, key=lambda item: item[0])[1]


def _summary_mentions_move(summary, move):
    """Match a move by SAN without requiring or accepting a move number."""
    san = _format_summary_move(move)
    pattern = rf"(?<![A-Za-z0-9]){re.escape(san)}(?![A-Za-z0-9])"
    return re.search(pattern, summary, re.IGNORECASE) is not None


def _validate_summary(summary, move_data):
    """Reject prose whose side/classification claims contradict engine facts."""
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 700:
        return False
    if _MOVE_NUMBER_RE.search(summary):
        return False
    if _SUMMARY_INVENTORY_RE.search(summary):
        return False

    turning_points = _summary_turning_points(move_data)
    if turning_points:
        lower = summary.lower()
        matching_points = [
            point for point in turning_points
            if _summary_mentions_move(summary, move_data[point["id"]])
        ]
        if not matching_points or not _SUMMARY_NARRATIVE_RE.search(summary):
            return False
        if not any(
            isinstance(point.get("turn"), str)
            and point["turn"].lower() in lower
            for point in matching_points
        ):
            return False

    context = _summary_context(move_data)
    checkmate_move = context.get("checkmate_move")
    if checkmate_move:
        mate = move_data[checkmate_move["id"]]
        mate_san = mate.get("san") or mate.get("facts", {}).get("played")
        mentions_mate = _summary_mentions_move(summary, mate)
        if isinstance(mate_san, str):
            mentions_mate = mentions_mate or mate_san.lower() in summary.lower()
        if not mentions_mate:
            return False

    counts = _classification_counts(move_data)
    for sentence_match in re.finditer(
        r".+?(?:[!?]+|(?<!\.)\.(?=\s|$)|$)", summary
    ):
        sentence = sentence_match.group(0)
        if not sentence.strip():
            continue
        for classification, pattern in _SUMMARY_CLASS_PATTERNS.items():
            for claim in pattern.finditer(sentence):
                side = _claim_side(sentence, claim.start())
                if side is None:
                    return False
                actual = counts[side].get(classification, 0)
                claimed = _nearby_claimed_count(sentence, claim.start())
                if claimed is not None:
                    if claimed != actual:
                        return False
                elif actual == 0:
                    return False
    allowed = set()
    for move in move_data:
        allowed.update(_allowed_tokens(move.get("prompt_str", "")))
    lower = summary.lower()
    for square in _SQUARE_RE.findall(lower):
        if square not in allowed:
            return False
    return True


def _allowed_tokens(prompt_str):
    tokens = set()
    lower = prompt_str.lower()
    for word in _PIECE_WORDS:
        if word in lower:
            tokens.add(word)
    for sq in _SQUARE_RE.findall(lower):
        tokens.add(sq)
    return tokens


def _citation_tokens(facts):
    """Concrete verified tokens a notable comment may use as its reason."""
    tokens = set()

    def add_squares(value):
        if isinstance(value, str):
            tokens.update(_SQUARE_RE.findall(value.lower()))
        elif isinstance(value, list):
            for item in value:
                add_squares(item)

    for key in ("best", "best_line", "refutation", "missed_capture",
                "runner_up", "forcing_line"):
        add_squares(facts.get(key))

    consequence = facts.get("capture_consequence") or {}
    add_squares(consequence.get("piece"))
    add_squares(consequence.get("recapture"))
    add_squares(consequence.get("line"))

    hanging = [*(facts.get("hanging") or []),
               *(facts.get("runner_up_hanging") or [])]
    for item in hanging:
        lower = item.lower()
        add_squares(lower)
        for word in _PIECE_WORDS:
            if word in lower:
                tokens.add(word)
        if "pinned" in lower:
            tokens.add("pinned")

    if facts.get("is_sacrifice"):
        tokens.add("sacrifice")
    if facts.get("king_in_check"):
        tokens.add("check")
    return tokens


def _addresses_capture_consequence(comment, facts):
    """Require a concrete recapture and material explanation when supplied."""
    consequence = facts.get("capture_consequence")
    if not consequence:
        return True

    lower = comment.lower()
    piece = str(consequence.get("piece", "")).lower()
    recapture = str(consequence.get("recapture", "")).lower()
    if not piece or not recapture or piece not in lower or recapture not in lower:
        return False

    delta = consequence.get("material_delta")
    if delta > 0:
        return bool(re.search(r"\b(?:win|wins|won|gain|gains|ahead|material)\b", lower))
    if delta < 0:
        return bool(re.search(
            r"\b(?:lose|loses|lost|cost|costs|costing|give|gives|sacrifice|material)\b",
            lower,
        ))
    return bool(re.search(r"\b(?:equal|even|trade|exchange)\b", lower))


def _has_verified_citation(comment, move):
    if move["classification"] not in NOTABLE:
        return True
    available = _citation_tokens(move["facts"])
    if not available:
        return True
    lower = comment.lower()
    return any(re.search(rf"\b{re.escape(token)}\b", lower) for token in available)


def _validate_comment(comment, move):
    """Reject hallucinations and unjustified notable-move commentary."""
    if not isinstance(comment, str) or not comment or len(comment) > 500:
        return False
    if _MOVE_NUMBER_RE.search(comment):
        return False
    prompt_str = move["prompt_str"]
    lower = comment.lower()
    allowed = _allowed_tokens(prompt_str)
    for word in _PIECE_WORDS:
        if word in lower and word not in allowed:
            return False
    for sq in _SQUARE_RE.findall(lower):
        if sq not in allowed and sq not in prompt_str.lower():
            return False
    return (
        _has_verified_citation(comment, move)
        and _addresses_capture_consequence(comment, move["facts"])
    )



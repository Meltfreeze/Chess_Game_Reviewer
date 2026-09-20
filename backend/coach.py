"""
coach.py — Turns VERIFIED facts (from engine.py) into friendly text.
Gemini output is validated against engine facts; deterministic prose is the fallback.
"""

import json
import hashlib
import re

from backend.engine import NOTABLE, CRITICAL_CLASSES

_POSITIVE = {
    "Brilliant": "Brilliant! A striking move that most players would never spot.",
    "Great": "Great find — this was essentially the only move that kept your position healthy.",
    "Best": "The engine's top choice. Clean and accurate.",
    "Excellent": "Excellent — right in line with the best play here.",
    "Good": "A solid, sensible move.",
    "Book": "A well-known opening move.",
    "Miss": "You missed a stronger tactical opportunity here.",
}

_PIECE_WORDS = {"pawn", "knight", "bishop", "rook", "queen", "king"}
_SQUARE_RE = re.compile(r"\b[a-h][1-8]\b")
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


def template_comment(move):
    f = move["facts"]
    cls = move["classification"]

    if cls in _POSITIVE:
        base = _POSITIVE[cls]
        if cls in ("Brilliant", "Good") and f.get("is_sacrifice"):
            base = "Brilliant! A bold sacrifice that the engine confirms is strong."
            if cls == "Good":
                base = "A sound sacrifice that keeps the position healthy."
        if cls == "Miss" and f.get("missed_capture"):
            base = f"You missed the tactic {f['missed_capture']}."
        elif cls == "Miss" and f.get("best_line"):
            base = f"You missed the stronger continuation {' '.join(f['best_line'])}."
        elif cls == "Miss" and f.get("best"):
            base = f"You missed {f['best']} — a stronger move."
        elif cls == "Great" and f.get("runner_up_hanging"):
            base = (f"Great find — the runner-up {f['runner_up']} would leave your "
                    f"{f['runner_up_hanging'][0]} vulnerable.")
        elif cls == "Great" and f.get("runner_up"):
            base = (f"Great find — even the engine's runner-up {f['runner_up']} was "
                    "not enough to hold the position as well.")
        return base

    parts = []
    if cls == "Blunder":
        parts.append("This is a serious slip.")
    elif cls == "Mistake":
        parts.append("Not the best — this hands over some of your advantage.")
    else:
        parts.append("A slight inaccuracy.")

    reason = None
    if f.get("hanging"):
        hanging = f["hanging"][0]
        if "(pinned)" in hanging:
            reason = f"It leaves your {hanging.replace(' (pinned)', '')} pinned and hanging."
        else:
            reason = f"It leaves your {hanging} vulnerable."
    elif f.get("forcing_line"):
        reason = f"The forcing continuation is {' '.join(f['forcing_line'])}."
    elif f.get("missed_capture"):
        reason = f"You could have played {f['missed_capture']}."
    elif f.get("best_line"):
        reason = f"The engine preferred {' '.join(f['best_line'])}."
    elif f.get("refutation"):
        reason = f"The opponent can answer with {f['refutation']}."
    elif f.get("best"):
        reason = f"{f['best']} was stronger."
    elif f.get("king_in_check"):
        reason = "It leaves your king exposed to check."
    elif f.get("is_sacrifice"):
        reason = "The engine confirms this was a sacrifice that did not work."
    if reason:
        parts.append(reason)
    return " ".join(parts)


_SYSTEM = (
    "You are a warm, concise chess coach. You are given engine-VERIFIED facts "
    "about chess moves. Write plain-English commentary using ONLY those facts. "
    "Never invent threats, attacks, piece names, or squares that are not in the "
    "facts; name a move by the exact notation given (e.g. Nf3) rather than a piece "
    "type the facts do not name. No jargon dumps. Output strict JSON only.\n"
    "Blunder/Mistake/Inaccuracy/Miss/Great/Brilliant: say what happened and briefly "
    "why. A label by itself is invalid. Cite the most concrete available verified "
    "fact in this order: a pinned hanging piece; a forcing continuation; a missed "
    "capture; the engine's preferred continuation; the runner-up and why it fails; "
    "a verified sacrifice. The opponent's best reply is also a concrete reason when "
    "no richer continuation is available, including for Inaccuracies. "
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


def _move_prompt_payload(move, index):
    return {
        "id": index,
        "turn": move.get("turn"),
        "move_number": move.get("move_number"),
        "san": move.get("san") or move.get("facts", {}).get("played"),
        "classification": move.get("classification"),
        "facts": move.get("prompt_str", ""),
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


def _validate_summary(summary, move_data):
    """Reject prose whose side/classification claims contradict engine facts."""
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 700:
        return False
    if _SUMMARY_INVENTORY_RE.search(summary):
        return False

    turning_points = _summary_turning_points(move_data)
    if turning_points:
        lower = summary.lower()
        matching_points = [
            point for point in turning_points
            if _format_summary_move(move_data[point["id"]]).lower() in lower
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
        mate_label = _format_summary_move(move_data[checkmate_move["id"]]).lower()
        if mate_label not in summary.lower():
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
    prompt_str = move["prompt_str"]
    lower = comment.lower()
    allowed = _allowed_tokens(prompt_str)
    for word in _PIECE_WORDS:
        if word in lower and word not in allowed:
            return False
    for sq in _SQUARE_RE.findall(lower):
        if sq not in allowed and sq not in prompt_str.lower():
            return False
    return _has_verified_citation(comment, move)


def _select_notable(move_data, critical_moments=None, cap=24):
    idxs = [i for i, m in enumerate(move_data) if m["classification"] in NOTABLE]
    if critical_moments:
        for cm in critical_moments:
            ply = cm.get("ply", -1)
            if 0 <= ply < len(move_data) and ply not in idxs:
                idxs.append(ply)
    if move_data:
        worst = max(range(len(move_data)), key=lambda i: move_data[i]["cp_loss"])
        if worst not in idxs:
            idxs.append(worst)
    idxs = sorted(set(idxs))
    if len(idxs) > cap:
        idxs = sorted(idxs, key=lambda i: -move_data[i]["cp_loss"])[:cap]
        idxs = sorted(idxs)
    return idxs


def _select_brief(move_data, notable_idxs):
    """Routine moves that still get a short Gemini line."""
    notable_set = set(notable_idxs)
    brief = []
    for i, m in enumerate(move_data):
        if i in notable_set:
            continue
        if m["classification"] in ("Best", "Excellent", "Good", "Book"):
            brief.append(i)
    return brief[:20]


def generate_coach(move_data, gemini_client, critical_moments=None,
                   model="gemini-2.5-flash", _cache=None, status_out=None):
    if _cache is None:
        _cache = {}
    if status_out is None:
        status_out = {}

    key = _game_key(move_data)
    if key in _cache:
        cached = _cache[key]
        if len(cached) == 4:
            status_out.update(cached[3])
            return cached[:3]
        return cached

    comments = [template_comment(m) for m in move_data]
    notable = _select_notable(move_data, critical_moments)
    brief = _select_brief(move_data, notable)
    summary = _fallback_summary(move_data)

    if gemini_client is None:
        status = {
            "gemini_attempted": False,
            "generation_complete": False,
            "summary_generated": False,
            "summary_accepted": False,
            "requested_comments": len(notable) + len(brief),
            "generated_comments": 0,
            "accepted_comments": 0,
            "fallback_used": True,
        }
        result = (summary, comments, False)
        status_out.update(status)
        _cache[key] = (*result, status)
        return result

    summary_context = _summary_context(move_data)
    payload_notable = [_move_prompt_payload(move_data[i], i) for i in notable]
    payload_brief = [_move_prompt_payload(move_data[i], i) for i in brief]

    prompt = (
        "Review White and Black equally. Return JSON with:\n"
        '{"summary": "<1-2 sentence game overview>", '
        '"comments": {"<move_id>": "<friendly comment, 1-2 sentences>"}, '
        '"brief": {"<move_id>": "<short one-liner>"}}\n'
        f"Use comments for key moves ({len(payload_notable)} moves) and brief for "
        f"routine moves ({len(payload_brief)} moves). Key moves need a brief why; "
        f"routine moves need one line. Use ONLY provided facts. Every move names "
        f"the side that played it. The summary must tell the game's story in "
        f"chronological terms: name the decisive move (with its move number and "
        f"exact SAN), explain its verified consequence, and connect it to the "
        f"result. Focus on at most two turning points. Name White or Black "
        f"explicitly instead of saying 'you' or 'the opponent'. Do not enumerate "
        f"classification totals or write a report-card inventory of Book, Best, "
        f"Good, or other labels. Classification counts are supplied only to "
        f"validate factual side attribution, not as summary content.\n\n"
        f"SUMMARY FACTS: {json.dumps(summary_context)}\n"
        f"KEY MOVES: {json.dumps(payload_notable)}\n"
        f"ROUTINE MOVES: {json.dumps(payload_brief)}"
    )

    commentary_succeeded = False
    summary_generated = False
    summary_succeeded = False
    generated = set()
    accepted = set()
    gemini_attempted = False
    try:
        from google import genai
        gemini_attempted = True
        resp = gemini_client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        data = json.loads(resp.text.strip())
        generated_summary = data.get("summary")
        summary_generated = isinstance(generated_summary, str) and bool(generated_summary.strip())
        summary_succeeded = _validate_summary(generated_summary, move_data)
        if summary_succeeded:
            summary = generated_summary

        requested = set(notable) | set(brief)

        def apply_comments(candidates):
            if not isinstance(candidates, dict):
                return
            for raw_idx, candidate in candidates.items():
                try:
                    idx = int(raw_idx)
                    if not 0 <= idx < len(move_data):
                        continue
                    if idx in requested:
                        generated.add(idx)
                    if _validate_comment(candidate, move_data[idx]):
                        comments[idx] = candidate
                        accepted.add(idx)
                except Exception:
                    # One malformed entry must not prevent valid later entries
                    # in the same batch from replacing their fallbacks.
                    continue

        apply_comments(data.get("comments", {}))
        apply_comments(data.get("brief", {}))
        commentary_succeeded = summary_succeeded and requested.issubset(accepted)
    except Exception:
        # The deterministic comments above are the safe default. A failed API
        # call or malformed response must degrade to them, not break review.
        pass

    requested = set(notable) | set(brief)
    status = {
        "gemini_attempted": gemini_attempted,
        "generation_complete": summary_generated and requested.issubset(generated),
        "summary_generated": summary_generated,
        "summary_accepted": summary_succeeded,
        "requested_comments": len(requested),
        "generated_comments": len(generated),
        "accepted_comments": len(accepted & requested),
        "fallback_used": not commentary_succeeded,
    }
    result = (summary, comments, commentary_succeeded)
    status_out.update(status)
    _cache[key] = (*result, status)
    return result


def _move_key(move):
    h = hashlib.sha1()
    h.update(f'{move["fen_before"]}{move["uci"]}{move["classification"]}'.encode())
    return h.hexdigest()


def generate_move_comment(move, gemini_client, model="gemini-2.5-flash", _cache=None):
    """Coach a single move — the single-move counterpart to generate_coach.

    generate_coach batches a whole game into one Gemini call and keys its cache
    on the full move list, so it cannot comment on a move that was not part of
    the reviewed game. This takes one entry from engine.analyze_move and runs it
    through the same system prompt and fact validation. Falls back to
    template_comment on any Gemini failure (missing key, rate limit, bad JSON)
    so exploring the board never breaks on the free tier.
    """
    if _cache is None:
        _cache = {}

    key = _move_key(move)
    if key in _cache:
        return _cache[key]

    comment = template_comment(move)

    if gemini_client is not None:
        prompt = (
            'Return JSON with: {"comment": "<friendly comment>"}\n'
            f'Classification: {move["classification"]}\n'
            f'Facts: {move["prompt_str"]}'
        )
        try:
            from google import genai
            resp = gemini_client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=_SYSTEM,
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            candidate = json.loads(resp.text.strip()).get("comment")
            if _validate_comment(candidate, move):
                comment = candidate
        except Exception:
            pass

    _cache[key] = comment
    return comment


def _fallback_summary(move_data):
    context = _summary_context(move_data)

    if not move_data:
        return "Game reviewed. Step through the moves to see what happened."

    opening = context.get("opening")
    prefix = f"In the {opening}, " if opening else ""

    negative = [
        move for move in move_data
        if move.get("classification") in _SUMMARY_NEGATIVE_CLASSES
    ]
    decisive = max(
        negative,
        key=lambda move: (
            float(move.get("cp_loss") or 0),
            _SUMMARY_CLASS_PRIORITY.get(move.get("classification"), 0),
        ),
        default=None,
    )
    mate_move = context.get("checkmate_move")

    if decisive:
        side = decisive.get("turn") or "The mover"
        move_label = _format_summary_move(decisive)
        classification = decisive.get("classification", "error").lower()
        if mate_move:
            winner = context.get("checkmate_by") or "The winner"
            mate_label = _format_summary_move(move_data[mate_move["id"]])
            return (
                f"{prefix}{side}'s {move_label} was the decisive {classification}, "
                f"allowing {winner} to finish with {mate_label}."
            )
        consequence = _fallback_consequence(decisive)
        if consequence:
            return (
                f"{prefix}{side}'s {move_label} was the key {classification}, "
                f"{consequence}."
            )
        return (
            f"{prefix}{side}'s {move_label} was the decisive {classification} "
            "and the game's key turning point."
        )

    positive = [
        move for move in move_data
        if move.get("classification") in {"Brilliant", "Great"}
    ]
    if positive:
        standout = max(positive, key=lambda move: float(move.get("cp_loss") or 0))
        return (
            f"{prefix}{standout.get('turn', 'The mover')}'s "
            f"{_format_summary_move(standout)} was the game's standout "
            f"{standout.get('classification', 'move').lower()}."
        )

    if mate_move:
        return (
            f"{prefix}{context.get('checkmate_by', 'The winner')} converted the game "
            f"with {_format_summary_move(move_data[mate_move['id']])}."
        )
    return f"{prefix}the game had no single decisive classified turning point."


def _format_summary_move(move):
    san = move.get("san") or move.get("facts", {}).get("played") or "the move"
    move_number = move.get("move_number")
    if not move_number:
        return san
    separator = "." if move.get("turn") == "White" else "..."
    return f"{move_number}{separator}{san}"


def _fallback_consequence(move):
    facts = move.get("facts", {})
    hanging = facts.get("hanging") or []
    if hanging:
        target = str(hanging[0]).replace(" (pinned)", "")
        if "(pinned)" in str(hanging[0]):
            return f"leaving the {target} pinned and vulnerable"
        return f"leaving the {target} vulnerable"
    if facts.get("forcing_line"):
        return f"running into {' '.join(facts['forcing_line'])}"
    if facts.get("refutation"):
        return f"allowing {facts['refutation']}"
    if facts.get("missed_capture"):
        return f"missing the stronger {facts['missed_capture']}"
    if facts.get("best"):
        return f"when {facts['best']} was stronger"
    return None

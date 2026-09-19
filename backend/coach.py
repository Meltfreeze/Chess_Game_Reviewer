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


def generate_coach(move_data, player_color, gemini_client, critical_moments=None,
                   model="gemini-2.5-flash", _cache=None):
    if _cache is None:
        _cache = {}

    key = _game_key(move_data)
    if key in _cache:
        return _cache[key]

    comments = [template_comment(m) for m in move_data]
    notable = _select_notable(move_data, critical_moments)
    brief = _select_brief(move_data, notable)
    summary = _fallback_summary(move_data, player_color)

    if gemini_client is None:
        result = (summary, comments, False)
        _cache[key] = result
        return result

    payload_notable = [{"id": i, "classification": move_data[i]["classification"],
                        "facts": move_data[i]["prompt_str"]} for i in notable]
    payload_brief = [{"id": i, "classification": move_data[i]["classification"],
                      "facts": move_data[i]["prompt_str"]} for i in brief]

    prompt = (
        f"Player under review: {player_color}. Return JSON with:\n"
        '{"summary": "<1-2 sentence game overview>", '
        '"comments": {"<move_id>": "<friendly comment, 1-2 sentences>"}, '
        '"brief": {"<move_id>": "<short one-liner>"}}\n'
        f"Use comments for key moves ({len(payload_notable)} moves) and brief for "
        f"routine moves ({len(payload_brief)} moves). Key moves need a brief why; "
        f"routine moves need one line. Use ONLY provided facts.\n\n"
        f"KEY MOVES: {json.dumps(payload_notable)}\n"
        f"ROUTINE MOVES: {json.dumps(payload_brief)}"
    )

    all_comments_succeeded = False
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
        data = json.loads(resp.text.strip())
        summary = data.get("summary", summary)
        accepted = set()

        def apply_comments(generated):
            if not isinstance(generated, dict):
                return
            for raw_idx, candidate in generated.items():
                try:
                    idx = int(raw_idx)
                    if not 0 <= idx < len(move_data):
                        continue
                    if _validate_comment(candidate, move_data[idx]):
                        comments[idx] = candidate
                        accepted.add(idx)
                except Exception:
                    # One malformed entry must not prevent valid later entries
                    # in the same batch from replacing their fallbacks.
                    continue

        apply_comments(data.get("comments", {}))
        apply_comments(data.get("brief", {}))
        requested = set(notable) | set(brief)
        all_comments_succeeded = requested.issubset(accepted)
    except Exception:
        # The deterministic comments above are the safe default. A failed API
        # call or malformed response must degrade to them, not break review.
        pass

    result = (summary, comments, all_comments_succeeded)
    _cache[key] = result
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


def _fallback_summary(move_data, player_color):
    mine = [m for m in move_data if m["turn"] == player_color]
    blunders = sum(1 for m in mine if m["classification"] == "Blunder")
    mistakes = sum(1 for m in mine if m["classification"] == "Mistake")
    misses = sum(1 for m in mine if m["classification"] == "Miss")
    good = sum(1 for m in mine if m["classification"] in
               ("Best", "Excellent", "Brilliant", "Great"))

    if not mine:
        return "Game reviewed. Step through the moves to see what happened."

    def plural(k, word):
        return f"{k} {word}" + ("" if k == 1 else "s")

    parts = []
    if blunders == 0 and mistakes == 0 and misses == 0:
        return (f"Clean game — no major errors, with {plural(good, 'strong move')}. "
                f"Well played!")
    if good:
        parts.append(f"{plural(good, 'strong move')}")
    if blunders:
        parts.append(plural(blunders, "blunder"))
    if mistakes:
        parts.append(plural(mistakes, "mistake"))
    if misses:
        parts.append(plural(misses, "missed opportunity"))
    return f"You played {', '.join(parts)}. Review the marked moves below."

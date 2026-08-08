"""
coach.py — Turns VERIFIED facts (from engine.py) into friendly text.
Gemini is required; output is validated against engine facts.
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
    san = f["played"]

    if cls in _POSITIVE:
        base = _POSITIVE[cls]
        if cls == "Brilliant" and f.get("is_capture"):
            base = "Brilliant! A bold sacrifice that the engine confirms is strong."
        if cls == "Miss" and f.get("missed_capture"):
            base = f"You missed the tactic {f['missed_capture']}."
        elif cls == "Miss" and f.get("best"):
            base = f"You missed {f['best']} — a stronger continuation."
        return base

    parts = []
    if cls == "Blunder":
        parts.append("This is a serious slip.")
    elif cls == "Mistake":
        parts.append("Not the best — this hands over some of your advantage.")
    else:
        parts.append("A slight inaccuracy.")

    if f.get("hanging"):
        parts.append(f"It leaves your {f['hanging'][0]} undefended.")
    if f.get("refutation"):
        parts.append(f"The opponent can answer with {f['refutation']}.")
    if f.get("best"):
        parts.append(f"{f['best']} was stronger.")
    if f.get("missed_capture"):
        parts.append(f"You could have played {f['missed_capture']}.")
    return " ".join(parts)


_SYSTEM = (
    "You are a warm, concise chess coach. You are given engine-VERIFIED facts "
    "about chess moves. Write ONE short, plain-English sentence for each move, "
    "using ONLY the given facts. Never invent threats, attacks, piece names, or "
    "squares that are not in the facts. No jargon dumps. Output strict JSON only."
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


def _validate_comment(comment, prompt_str):
    """Reject Gemini output that mentions pieces/squares absent from facts."""
    if not comment or len(comment) > 500:
        return False
    lower = comment.lower()
    allowed = _allowed_tokens(prompt_str)
    for word in _PIECE_WORDS:
        if word in lower and word not in allowed:
            return False
    for sq in _SQUARE_RE.findall(lower):
        if sq not in allowed and sq not in prompt_str.lower():
            return False
    return True


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

    if gemini_client is None:
        raise ValueError("GEMINI_API_KEY is required for game review coaching")

    comments = [template_comment(m) for m in move_data]
    notable = _select_notable(move_data, critical_moments)
    brief = _select_brief(move_data, notable)
    summary = _fallback_summary(move_data, player_color)

    payload_notable = [{"id": i, "facts": move_data[i]["prompt_str"]} for i in notable]
    payload_brief = [{"id": i, "facts": move_data[i]["prompt_str"]} for i in brief]

    prompt = (
        f"Player under review: {player_color}. Return JSON with:\n"
        '{"summary": "<1-2 sentence game overview>", '
        '"comments": {"<move_id>": "<one friendly sentence>"}, '
        '"brief": {"<move_id>": "<short one-liner>"}}\n'
        f"Use comments for key moves ({len(payload_notable)} moves) and brief for "
        f"routine moves ({len(payload_brief)} moves). Use ONLY provided facts.\n\n"
        f"KEY MOVES: {json.dumps(payload_notable)}\n"
        f"ROUTINE MOVES: {json.dumps(payload_brief)}"
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
        data = json.loads(resp.text.strip())
        summary = data.get("summary", summary)
        for k, v in data.get("comments", {}).items():
            try:
                idx = int(k)
                if _validate_comment(v, move_data[idx]["prompt_str"]):
                    comments[idx] = v
            except (ValueError, IndexError):
                pass
        for k, v in data.get("brief", {}).items():
            try:
                idx = int(k)
                if _validate_comment(v, move_data[idx]["prompt_str"]):
                    comments[idx] = v
            except (ValueError, IndexError):
                pass
    except Exception as exc:
        raise ValueError(f"Gemini coaching failed: {exc}") from exc

    result = (summary, comments)
    _cache[key] = result
    return result


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

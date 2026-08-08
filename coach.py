"""
coach.py — Turns VERIFIED facts (from engine.py) into friendly text.

Two paths, chosen to respect a free-tier key:
  1. template_comment(): pure Python, no API. Used for ordinary moves and as a
     fallback. It can only state things that are true, because it reads the
     verified facts dict.
  2. generate_coach(): ONE Gemini call for the whole game, and only for the
     handful of "notable" moves (blunders, mistakes, brilliancies...). The model
     is told to rephrase the given facts and invent nothing. Everything is
     cached on the game's move list so re-opening a game costs zero calls.

Because the model never sees the board and is handed only engine-verified facts,
it cannot say "the rook is attacked" unless a rook really is attacked.
"""

import json
import hashlib
from engine import NOTABLE

# --------------------------------------------------------------------------
# Local, no-API templates
# --------------------------------------------------------------------------
_POSITIVE = {
    "Brilliant": "Brilliant! A striking move that most players would never spot.",
    "Great": "Great find — this was essentially the only move that kept your position healthy.",
    "Best": "The engine's top choice. Clean and accurate.",
    "Excellent": "Excellent — right in line with the best play here.",
    "Good": "A solid, sensible move.",
    "Book": "A well-known opening move.",
}


def template_comment(move):
    """A truthful one-liner built only from verified facts (no API)."""
    f = move["facts"]
    cls = move["classification"]
    san = f["played"]

    if cls in _POSITIVE:
        base = _POSITIVE[cls]
        if cls == "Brilliant" and f.get("is_capture"):
            base = "Brilliant! A bold sacrifice that the engine confirms is strong."
        return base

    # Mistake-class: describe the concrete, verified consequence
    parts = []
    if cls == "Blunder":
        parts.append("This is a serious slip.")
    elif cls == "Mistake":
        parts.append("Not the best — this hands over some of your advantage.")
    else:  # Inaccuracy
        parts.append("A slight inaccuracy.")

    if f.get("hanging"):
        parts.append(f"It leaves your {f['hanging'][0]} undefended.")
    if f.get("refutation"):
        parts.append(f"The opponent can answer with {f['refutation']}.")
    if f.get("best"):
        parts.append(f"{f['best']} was stronger.")
    return " ".join(parts)


# --------------------------------------------------------------------------
# One batched Gemini call, notable moves only, grounded in facts
# --------------------------------------------------------------------------
_SYSTEM = (
    "You are a warm, concise chess coach. You are given engine-VERIFIED facts "
    "about a few moves. Write ONE short, plain-English sentence for each, using "
    "ONLY the given facts. Never invent threats, attacks, or piece names that "
    "are not in the facts. No jargon dumps. Output strict JSON only."
)


def _game_key(move_data):
    h = hashlib.sha1()
    for m in move_data:
        h.update(f'{m["uci"]}{m["classification"]}'.encode())
    return h.hexdigest()


def _select_notable(move_data, cap=16):
    """Notable moves + always the single worst move, capped for the free tier."""
    idxs = [i for i, m in enumerate(move_data) if m["classification"] in NOTABLE]
    if move_data:
        worst = max(range(len(move_data)), key=lambda i: move_data[i]["cp_loss"])
        if worst not in idxs:
            idxs.append(worst)
    idxs = sorted(set(idxs))
    if len(idxs) > cap:                      # keep the biggest swings
        idxs = sorted(idxs, key=lambda i: -move_data[i]["cp_loss"])[:cap]
        idxs = sorted(idxs)
    return idxs


def generate_coach(move_data, player_color, gemini_client, model="gemini-2.5-flash",
                   _cache={}):
    """
    Returns (summary_str, comments_list) where comments_list[i] is the comment
    for move_data[i]. Makes at most ONE API call per distinct game.
    """
    key = _game_key(move_data)
    if key in _cache:
        return _cache[key]

    # Start every move with a truthful local template.
    comments = [template_comment(m) for m in move_data]

    notable = _select_notable(move_data)
    summary = _fallback_summary(move_data, player_color)

    if gemini_client is not None and notable:
        payload = [{"id": i, "facts": move_data[i]["prompt_str"]} for i in notable]
        prompt = (
            f"Player under review: {player_color}. Here are verified facts for "
            f"{len(payload)} key moves. Return JSON:\n"
            '{"summary": "<1-2 sentence game overview>", '
            '"comments": {"<id>": "<one friendly sentence>"}}\n\n'
            f"FACTS: {json.dumps(payload)}"
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
                    comments[int(k)] = v
                except (ValueError, IndexError):
                    pass
        except Exception:
            # keep templates + fallback summary; never crash the review
            pass

    _cache[key] = (summary, comments)
    return summary, comments


def _fallback_summary(move_data, player_color):
    mine = [m for m in move_data if m["turn"] == player_color]
    blunders = sum(1 for m in mine if m["classification"] == "Blunder")
    mistakes = sum(1 for m in mine if m["classification"] == "Mistake")
    good = sum(1 for m in mine if m["classification"] in ("Best", "Excellent", "Brilliant", "Great"))
    if not mine:
        return "Game reviewed. Step through the moves to see what happened."

    def plural(k, word):
        return f"{k} {word}" + ("" if k == 1 else "s")

    if blunders == 0 and mistakes == 0:
        return (f"Clean game — no blunders or mistakes, with {plural(good, 'strong move')}. "
                f"Well played!")
    return (f"You played {plural(good, 'strong move')}, but {plural(blunders, 'blunder')} "
            f"and {plural(mistakes, 'mistake')} cost you. Review the marked moves below.")

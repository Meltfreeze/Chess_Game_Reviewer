"""Deterministic coaching prose used when generated commentary is unavailable."""

from .prompts import _SUMMARY_CLASS_PRIORITY, _SUMMARY_NEGATIVE_CLASSES, _format_summary_move, _summary_context

_POSITIVE = {
    "Brilliant": "Brilliant! A striking move that most players would never spot.",
    "Great": "Great find — this was essentially the only move that kept your position healthy.",
    "Best": "The engine's top choice. Clean and accurate.",
    "Excellent": "Excellent — right in line with the best play here.",
    "Good": "A solid, sensible move.",
    "Book": "A well-known opening move.",
    "Miss": "You missed a stronger tactical opportunity here.",
}


def _capture_consequence_comment(move):
    """Render an engine-verified recapture consequence without inventing tactics."""
    consequence = move["facts"].get("capture_consequence")
    if not consequence:
        return None

    played = move["facts"].get("played", "This capture")
    piece = consequence["piece"]
    recapture = consequence["recapture"]
    delta = consequence["material_delta"]

    if delta > 0:
        return (
            f"{played} wins {delta} points of material even after {recapture} "
            f"takes the {piece}."
        )
    if delta < 0:
        cost = abs(delta)
        if move["classification"] in _POSITIVE:
            evaluation = consequence["eval_after"]
            side = move.get("turn", "The mover")
            if evaluation > 0.8:
                result = f"still leaves {side} ahead"
            elif evaluation < -0.8:
                result = f"still leaves {side} worse"
            else:
                result = "still leaves the position roughly level"
            return (
                f"Although {recapture} takes the {piece} and costs {cost} points "
                f"of material, the engine line {result}."
            )
        return f"{recapture} takes the {piece}, costing {cost} points of material."
    return (
        f"After {recapture} takes the {piece}, the exchange is even."
    )


def template_comment(move):
    f = move["facts"]
    cls = move["classification"]
    capture_consequence = _capture_consequence_comment(move)

    if capture_consequence:
        if cls == "Great":
            return f"Great find — {capture_consequence}"
        if cls == "Brilliant":
            return f"Brilliant! {capture_consequence}"
        if cls in ("Blunder", "Mistake"):
            prefix = "This is a serious slip." if cls == "Blunder" else "Not the best."
            return f"{prefix} {capture_consequence}"
        if cls == "Inaccuracy":
            return f"A slight inaccuracy. {capture_consequence}"
        return capture_consequence

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
    return move.get("san") or move.get("facts", {}).get("played") or "the move"


def _fallback_consequence(move):
    facts = move.get("facts", {})
    consequence = facts.get("capture_consequence")
    if consequence:
        piece = consequence["piece"]
        recapture = consequence["recapture"]
        delta = consequence["material_delta"]
        if delta > 0:
            return f"winning {delta} points of material even after {recapture} takes the {piece}"
        if delta < 0:
            return f"allowing {recapture} to take the {piece}, costing {abs(delta)} points of material"
        return f"allowing an even exchange after {recapture} takes the {piece}"
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

"""Gemini coaching orchestration and public compatibility façade."""

import hashlib
import json
import logging

from backend.engine import NOTABLE
from .fallbacks import _fallback_summary, template_comment
from .prompts import _SYSTEM, _compact_move_facts, _game_key, _move_prompt_payload, _select_notable, _summary_context
from .validation import _validate_comment, _validate_summary

logger = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

def generate_coach(move_data, gemini_client, critical_moments=None,
                   model=DEFAULT_GEMINI_MODEL, _cache=None, status_out=None):
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
    notable = _select_notable(move_data)
    summary = _fallback_summary(move_data)

    if gemini_client is None:
        status = {
            "gemini_attempted": False,
            "generation_complete": False,
            "summary_generated": False,
            "summary_accepted": False,
            "requested_comments": len(notable),
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

    prompt = (
        "Review White and Black equally. Return JSON with:\n"
        '{"summary": "<1-2 sentence game overview>", '
        '"comments": {"<move_id>": "<friendly comment, 1-2 sentences>"}}\n'
        f"Write comments for the {len(payload_notable)} key moves. "
        f"Each needs a brief why. Use ONLY provided facts. Every move names "
        f"the side that played it. The summary must tell the game's story in "
        f"chronological terms: name the decisive move by its exact SAN without a "
        f"move number, explain its verified consequence, and connect it to the "
        f"result. Focus on at most two turning points. Name White or Black "
        f"explicitly instead of saying 'you' or 'the opponent'. Do not enumerate "
        f"classification totals or write a report-card inventory of Book, Best, "
        f"Good, or other labels. Classification counts are supplied only to "
        f"validate factual side attribution, not as summary content.\n\n"
        f"SUMMARY FACTS: {json.dumps(summary_context, separators=(',', ':'))}\n"
        f"KEY MOVES: {json.dumps(payload_notable, separators=(',', ':'))}"
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

        requested = set(notable)

        def apply_comments(candidates):
            if not isinstance(candidates, dict):
                return
            for raw_idx, candidate in candidates.items():
                try:
                    idx = int(raw_idx)
                    if not 0 <= idx < len(move_data):
                        continue
                    if idx not in requested:
                        continue
                    generated.add(idx)
                    if _validate_comment(candidate, move_data[idx]):
                        comments[idx] = candidate
                        accepted.add(idx)
                except Exception:
                    # One malformed entry must not prevent valid later entries
                    # in the same batch from replacing their fallbacks.
                    continue

        apply_comments(data.get("comments", {}))
        commentary_succeeded = summary_succeeded and requested.issubset(accepted)
    except Exception:
        # The deterministic comments above are the safe default. A failed API
        # call or malformed response must degrade to them, not break review.
        logger.exception("Gemini game commentary generation failed")

    requested = set(notable)
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



def generate_move_comment(move, gemini_client, model=DEFAULT_GEMINI_MODEL, _cache=None):
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
            f'Move: {json.dumps(_move_prompt_payload(move, 0), separators=(",", ":"))}'
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
            logger.exception("Gemini move commentary generation failed")

    _cache[key] = comment
    return comment



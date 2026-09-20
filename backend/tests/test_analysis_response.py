"""Analysis response fields added after engine analysis completes."""

import asyncio
import json

from backend import main


class _AnalysisServiceStub:
    def analyze_streaming(self, *_args, **_kwargs):
        yield "complete", {
            "move_data": [],
            "stats": {},
            "meta": {},
            "hist": [],
            "critical_moments": [],
        }


async def _response_body(response):
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


def test_analyze_complete_event_includes_commentary_status(monkeypatch):
    monkeypatch.setattr(main.AnalysisService, "get", lambda: _AnalysisServiceStub())
    monkeypatch.setattr(main, "_get_gemini", lambda: object())
    monkeypatch.setattr(
        main.coach_mod,
        "generate_coach",
        lambda *_args, **_kwargs: ("Summary", [], False),
    )

    response = main.analyze_game(main.AnalyzeRequest(pgn="1. e4", depth=8))
    body = asyncio.run(_response_body(response))
    event = next(block for block in body.split("\n\n") if "event: complete" in block)
    payload = json.loads(next(
        line.removeprefix("data: ")
        for line in event.splitlines()
        if line.startswith("data: ")
    ))

    assert payload["commentary_succeeded"] is False
    assert payload["all_comments_succeeded"] is False
    assert payload["commentary_status"]["fallback_used"] is True
    assert payload["commentary_status"]["gemini_attempted"] is True
    assert "player_color" not in payload

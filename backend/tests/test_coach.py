"""Fact-citation enforcement for batch and single-move coaching."""

import json
import sys
import types

from backend.coach import generate_coach, generate_move_comment, template_comment


class _FakeModels:
    def __init__(self, payload):
        self.payload = payload

    def generate_content(self, **_kwargs):
        return types.SimpleNamespace(text=json.dumps(self.payload))


class _FakeClient:
    def __init__(self, payload):
        self.models = _FakeModels(payload)


def _install_fake_genai(monkeypatch):
    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    genai.types = types.SimpleNamespace(
        GenerateContentConfig=lambda **kwargs: kwargs
    )
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)


def _blunder_move():
    return {
        "turn": "White",
        "uci": "d1d4",
        "fen_before": "fixture-fen",
        "classification": "Blunder",
        "cp_loss": 250,
        "facts": {
            "played": "Qd4",
            "class": "Blunder",
            "eval_before": 0.2,
            "eval_after": -2.3,
            "hanging": ["queen on d4 (pinned)"],
            "refutation": "Nxd4",
            "best": "Nf3",
            "is_sacrifice": False,
        },
        "prompt_str": (
            "Qd4 (Blunder); engine preferred Nf3; leaves hanging: "
            "queen on d4 (pinned); opponent can reply Nxd4"
        ),
    }


def test_batch_rejects_unjustified_notable_comment(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()
    _, comments = generate_coach(
        [move],
        "White",
        _FakeClient({"summary": "Summary", "comments": {"0": "This is a mistake."}}),
        _cache={},
    )

    assert comments[0] != "This is a mistake."
    assert "queen" in comments[0].lower()
    assert "pinned" in comments[0].lower()


def test_batch_keeps_comment_that_cites_verified_fact(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()
    justified = "Your pinned queen on d4 is left vulnerable."
    _, comments = generate_coach(
        [move],
        "White",
        _FakeClient({"summary": "Summary", "comments": {"0": justified}}),
        _cache={},
    )

    assert comments[0] == justified


def test_single_move_applies_the_same_citation_check(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()

    rejected = generate_move_comment(
        move,
        _FakeClient({"comment": "This is a mistake."}),
        _cache={},
    )
    justified = "The pinned queen on d4 cannot escape the threat."
    accepted = generate_move_comment(
        move,
        _FakeClient({"comment": justified}),
        _cache={},
    )

    assert rejected != "This is a mistake."
    assert "queen" in rejected.lower()
    assert accepted == justified


def test_batch_without_gemini_returns_fact_based_fallback():
    move = _blunder_move()
    summary, comments = generate_coach([move], "White", None, _cache={})

    assert summary
    assert "queen" in comments[0].lower()
    assert "pinned" in comments[0].lower()


def test_fallback_uses_forcing_line_and_verified_sacrifice():
    forcing = {
        "classification": "Mistake",
        "facts": {
            "played": "Qd4",
            "forcing_line": ["Nxd4", "exd4", "Qxd4"],
        },
    }
    sacrifice = {
        "classification": "Brilliant",
        "facts": {
            "played": "Rxf7+",
            "is_sacrifice": True,
        },
    }

    assert "Nxd4 exd4 Qxd4" in template_comment(forcing)
    assert "sacrifice" in template_comment(sacrifice).lower()

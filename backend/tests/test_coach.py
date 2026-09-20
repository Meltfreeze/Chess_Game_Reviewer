"""Fact-citation enforcement for batch and single-move coaching."""

import json
import sys
import types

from backend.coach import (
    DEFAULT_GEMINI_MODEL,
    generate_coach,
    generate_move_comment,
    template_comment,
)


class _FakeModels:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(text=json.dumps(self.payload))


class _FakeClient:
    def __init__(self, payload):
        self.models = _FakeModels(payload)


class _FailingModels:
    def generate_content(self, **_kwargs):
        raise RuntimeError("provider rejected test key")


class _FailingClient:
    def __init__(self):
        self.models = _FailingModels()


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


def _scholars_mate_moves():
    return [
        {
            "turn": "White",
            "move_number": 3,
            "san": "Qh5",
            "uci": "d1h5",
            "classification": "Inaccuracy",
            "cp_loss": 70,
            "facts": {
                "played": "Qh5",
                "class": "Inaccuracy",
                "opening": "Bishop's Opening",
            },
            "prompt_str": "Qh5 (Inaccuracy); opening: Bishop's Opening",
        },
        {
            "turn": "Black",
            "move_number": 3,
            "san": "Nf6",
            "uci": "g8f6",
            "classification": "Blunder",
            "cp_loss": 1000,
            "facts": {
                "played": "Nf6",
                "class": "Blunder",
                "opening": "Bishop's Opening",
            },
            "prompt_str": "Nf6 (Blunder); opening: Bishop's Opening; opponent can reply Qxf7#",
        },
        {
            "turn": "White",
            "move_number": 4,
            "san": "Qxf7#",
            "uci": "h5f7",
            "classification": "Best",
            "cp_loss": 0,
            "facts": {
                "played": "Qxf7#",
                "class": "Best",
                "opening": "Bishop's Opening",
            },
            "prompt_str": "Qxf7# (Best); opening: Bishop's Opening; gives check",
        },
    ]


def test_batch_rejects_unjustified_notable_comment(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()
    _, comments, commentary_succeeded = generate_coach(
        [move],
        _FakeClient({"summary": "Summary", "comments": {"0": "This is a mistake."}}),
        _cache={},
    )

    assert comments[0] != "This is a mistake."
    assert "queen" in comments[0].lower()
    assert "pinned" in comments[0].lower()
    assert not commentary_succeeded


def test_batch_keeps_comment_that_cites_verified_fact(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()
    justified = "Your pinned queen on d4 is left vulnerable."
    status = {}
    _, comments, commentary_succeeded = generate_coach(
        [move],
        _FakeClient({
            "summary": "White's Qd4 was the decisive blunder, leaving the queen pinned.",
            "comments": {"0": justified},
        }),
        _cache={},
        status_out=status,
    )

    assert comments[0] == justified
    assert commentary_succeeded
    assert status["generation_complete"] is True
    assert status["fallback_used"] is False
    assert status["accepted_comments"] == 1


def test_batch_fails_status_when_summary_falls_back(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()
    justified = "Your pinned queen on d4 is left vulnerable."

    status = {}
    summary, comments, commentary_succeeded = generate_coach(
        [move],
        _FakeClient({
            "summary": "Black made one blunder.",
            "comments": {"0": justified},
        }),
        _cache={},
        status_out=status,
    )

    assert summary == (
        "White's Qd4 was the key blunder, leaving the queen on d4 pinned and vulnerable."
    )
    assert comments[0] == justified
    assert not commentary_succeeded
    assert status["generation_complete"] is True
    assert status["summary_generated"] is True
    assert status["summary_accepted"] is False
    assert status["fallback_used"] is True


def test_cached_commentary_preserves_status_without_another_gemini_call(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()
    client = _FakeClient({
        "summary": "White's Qd4 was the decisive blunder, leaving the queen pinned.",
        "comments": {"0": "Your pinned queen on d4 is left vulnerable."},
    })
    cache = {}
    first_status = {}
    second_status = {}

    generate_coach([move], client, _cache=cache, status_out=first_status)
    generate_coach([move], client, _cache=cache, status_out=second_status)

    assert len(client.models.calls) == 1
    assert second_status == first_status


def test_batch_fails_status_when_a_requested_comment_is_missing(monkeypatch):
    _install_fake_genai(monkeypatch)
    first = _blunder_move()
    second = {**_blunder_move(), "uci": "d1d3"}
    justified = "Your pinned queen on d4 is left vulnerable."

    _, comments, commentary_succeeded = generate_coach(
        [first, second],
        _FakeClient({"summary": "Summary", "comments": {"0": justified}}),
        _cache={},
    )

    assert comments[0] == justified
    assert comments[1] == template_comment(second)
    assert not commentary_succeeded


def test_single_move_applies_the_same_citation_check(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()

    rejected_client = _FakeClient({"comment": "This is a mistake."})
    rejected = generate_move_comment(
        move,
        rejected_client,
        _cache={},
    )
    justified = "The pinned queen on d4 cannot escape the threat."
    accepted_client = _FakeClient({"comment": justified})
    accepted = generate_move_comment(
        move,
        accepted_client,
        _cache={},
    )

    assert rejected != "This is a mistake."
    assert "queen" in rejected.lower()
    assert accepted == justified
    assert rejected_client.models.calls[0]["model"] == DEFAULT_GEMINI_MODEL
    assert accepted_client.models.calls[0]["model"] == DEFAULT_GEMINI_MODEL
    system_instruction = accepted_client.models.calls[0]["config"]["system_instruction"]
    assert "Never include move numbers" in system_instruction


def test_single_move_rejects_generated_move_number(monkeypatch):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()

    comment = generate_move_comment(
        move,
        _FakeClient({"comment": "On move 3, the pinned queen on d4 is vulnerable."}),
        _cache={},
    )

    assert comment == template_comment(move)
    assert "move 3" not in comment.lower()


def test_batch_without_gemini_returns_fact_based_fallback():
    move = _blunder_move()
    summary, comments, commentary_succeeded = generate_coach([move], None, _cache={})

    assert summary
    assert "queen" in comments[0].lower()
    assert "pinned" in comments[0].lower()
    assert not commentary_succeeded


def test_batch_logs_gemini_failure_and_preserves_fallback(monkeypatch, caplog):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()

    with caplog.at_level("ERROR", logger="backend.coach"):
        summary, comments, commentary_succeeded = generate_coach(
            [move], _FailingClient(), _cache={}
        )

    assert summary
    assert comments == [template_comment(move)]
    assert not commentary_succeeded
    assert "Gemini game commentary generation failed" in caplog.text
    assert "provider rejected test key" in caplog.text


def test_single_move_logs_gemini_failure_and_preserves_fallback(monkeypatch, caplog):
    _install_fake_genai(monkeypatch)
    move = _blunder_move()

    with caplog.at_level("ERROR", logger="backend.coach"):
        comment = generate_move_comment(move, _FailingClient(), _cache={})

    assert comment == template_comment(move)
    assert "Gemini move commentary generation failed" in caplog.text
    assert "provider rejected test key" in caplog.text


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


def test_summary_rejects_classification_attributed_to_wrong_side(monkeypatch):
    _install_fake_genai(monkeypatch)
    moves = _scholars_mate_moves()
    wrong = (
        "This game in the Bishop's Opening saw White make an Inaccuracy "
        "and then a Blunder, leading to a quick checkmate."
    )

    summary, _, _ = generate_coach(
        moves,
        _FakeClient({"summary": wrong, "comments": {}, "brief": {}}),
        _cache={},
    )

    assert summary != wrong
    assert summary == (
        "In the Bishop's Opening, Black's Nf6 was the decisive blunder, "
        "allowing White to finish with Qxf7#."
    )


def test_summary_accepts_verified_turning_point_narrative(monkeypatch):
    _install_fake_genai(monkeypatch)
    moves = _scholars_mate_moves()
    verified = (
        "In the Bishop's Opening, Black's Nf6 was the decisive blunder, "
        "allowing White to finish with Qxf7#."
    )

    summary, _, _ = generate_coach(
        moves,
        _FakeClient({"summary": verified, "comments": {}, "brief": {}}),
        _cache={},
    )

    assert summary == verified


def test_summary_and_comments_accept_san_without_move_numbers(monkeypatch):
    _install_fake_genai(monkeypatch)
    moves = _scholars_mate_moves()
    generated = (
        "After White played the inaccurate Qh5, Black committed a decisive "
        "blunder with Nf6, allowing White to win with Qxf7#."
    )
    client = _FakeClient({
        "summary": generated,
        "comments": {
            "0": "White's Qh5 is an inaccuracy in the Bishop's Opening.",
            "1": "Black blundered with Nf6, allowing White to reply with Qxf7#.",
        },
        "brief": {"2": "White plays Qxf7# to give check."},
    })
    status = {}

    summary, _, commentary_succeeded = generate_coach(
        moves, client, _cache={}, status_out=status
    )

    assert summary == generated
    assert commentary_succeeded
    assert status["summary_accepted"] is True
    assert status["fallback_used"] is False
    assert client.models.calls[0]["model"] == "gemini-3.5-flash-lite"


def test_summary_rejects_move_numbers(monkeypatch):
    _install_fake_genai(monkeypatch)
    moves = _scholars_mate_moves()
    generated = (
        "White played the inaccurate 3. Qh5, but Black blundered with 3... Nf6, "
        "allowing White to deliver checkmate with 4. Qxf7#."
    )
    status = {}

    summary, _, _ = generate_coach(
        moves,
        _FakeClient({"summary": generated, "comments": {}, "brief": {}}),
        _cache={},
        status_out=status,
    )

    assert summary != generated
    assert "3." not in summary
    assert "4." not in summary
    assert status["summary_accepted"] is False


def test_summary_rejects_generic_text_that_omits_the_game_story(monkeypatch):
    _install_fake_genai(monkeypatch)
    moves = _scholars_mate_moves()
    generic = "The Bishop's Opening produced an exciting game with a quick checkmate."

    summary, _, _ = generate_coach(
        moves,
        _FakeClient({"summary": generic, "comments": {}, "brief": {}}),
        _cache={},
    )

    assert summary != generic
    assert "Black's Nf6" in summary
    assert "Qxf7#" in summary


def test_summary_rejects_classification_inventory_even_when_counts_are_correct(monkeypatch):
    _install_fake_genai(monkeypatch)
    moves = _scholars_mate_moves()
    wrong = (
        "The game was a Bishop's Opening where White played 1 Inaccuracy and "
        "1 Best move, leading to checkmate. Black played 1 Blunder."
    )

    summary, _, _ = generate_coach(
        moves,
        _FakeClient({"summary": wrong, "comments": {}, "brief": {}}),
        _cache={},
    )

    assert summary != wrong
    assert "Black's Nf6" in summary
    assert "Qxf7#" in summary


def test_batch_prompt_requires_a_turning_point_narrative(monkeypatch):
    _install_fake_genai(monkeypatch)
    client = _FakeClient({"summary": "Game reviewed.", "comments": {}, "brief": {}})

    generate_coach(_scholars_mate_moves(), client, _cache={})

    prompt = client.models.calls[0]["contents"]
    assert client.models.calls[0]["model"] == DEFAULT_GEMINI_MODEL
    assert '"turn": "White"' in prompt
    assert '"turn": "Black"' in prompt
    assert '"Inaccuracy": 1' in prompt
    assert '"Blunder": 1' in prompt
    assert '"checkmate_by": "White"' in prompt
    assert '"turning_points"' in prompt
    assert '"san": "Nf6"' in prompt
    assert '"san": "Qxf7#"' in prompt
    assert '"move_number"' not in prompt
    assert "without a move number" in prompt
    assert "Do not enumerate classification totals" in prompt


def test_batch_cache_is_shared_for_side_neutral_review():
    cache = {}
    moves = _scholars_mate_moves()

    first_summary, _, _ = generate_coach(moves, None, _cache=cache)
    second_summary, _, _ = generate_coach(moves, None, _cache=cache)

    assert len(cache) == 1
    assert first_summary == second_summary
    assert first_summary.startswith("In the Bishop's Opening, Black's Nf6")
    assert "White to finish with Qxf7#" in first_summary

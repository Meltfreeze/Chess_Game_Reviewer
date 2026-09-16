"""Verified coaching facts derived without additional engine searches."""

import json

import chess
import chess.engine

from backend.engine import (
    _hanging_pieces,
    _multipv_signals,
    analyze_game_streaming,
    analyze_move,
    extract_facts,
)


def _pv(board, *moves):
    scratch = board.copy(stack=False)
    line = []
    for uci in moves:
        move = chess.Move.from_uci(uci)
        assert move in scratch.legal_moves
        line.append(move)
        scratch.push(move)
    return line


def test_hanging_piece_is_annotated_when_pinned():
    board = chess.Board("4r1k1/8/8/8/8/8/4Q3/4K3 b - - 0 1")

    hanging = _hanging_pieces(board, chess.WHITE)

    assert ("queen", "e2", 4, True) in hanging


def test_multipv_signals_reuse_full_lines_and_runner_up():
    before = chess.Board()
    after = before.copy(stack=False)
    after.push_uci("e2e4")
    prev_info = [
        {"pv": _pv(before, "e2e4", "e7e5", "g1f3")},
        {"pv": _pv(before, "d2d4", "d7d5", "c2c4")},
    ]
    info = [
        {"pv": _pv(after, "c7c5", "g1f3", "d7d6", "d2d4")},
        {"pv": _pv(after, "e7e5", "g1f3")},
    ]

    signals = _multipv_signals(before, prev_info, after, info)

    assert signals["forcing_line"] == ["c5", "Nf3", "d6", "d4"]
    assert signals["runner_up"] == "d4"
    assert signals["runner_up_hanging"] == []


def test_runner_up_failure_uses_the_same_pinned_hanging_check():
    before = chess.Board("4r1k1/8/8/8/8/8/4Q2P/4K3 w - - 0 1")
    after = before.copy(stack=False)
    after.push_uci("e2e3")
    prev_info = [
        {"pv": _pv(before, "e2e3")},
        {"pv": _pv(before, "h2h3")},
    ]
    info = [{"pv": _pv(after, "e8e3", "e1f1")}]

    signals = _multipv_signals(before, prev_info, after, info)

    assert signals["runner_up"] == "h3"
    assert signals["runner_up_hanging"] == ["queen on e2 (pinned)"]


def test_fact_scoping_includes_inaccuracy_reply_but_not_forcing_line():
    board = chess.Board()
    facts, _ = extract_facts(
        board,
        chess.Move.from_uci("a2a3"),
        chess.Move.from_uci("e2e4"),
        20,
        -30,
        "Inaccuracy",
        opp_reply_san="e5",
        is_sacrifice=False,
        best_line=["e4", "e5", "Nf3"],
        forcing_line=["e5", "Nf3"],
    )

    assert facts["refutation"] == "e5"
    assert facts["best_line"] == ["e4", "e5", "Nf3"]
    assert "forcing_line" not in facts


class _StubEngine:
    def __init__(self):
        self.calls = 0

    @staticmethod
    def _line(board, first, max_plies=4):
        scratch = board.copy(stack=False)
        line = []
        move = first
        for _ in range(max_plies):
            if move not in scratch.legal_moves:
                break
            line.append(move)
            scratch.push(move)
            move = next(iter(scratch.legal_moves), None)
            if move is None:
                break
        return line

    def analyse(self, board, _limit, multipv=2):
        self.calls += 1
        legal = list(board.legal_moves)
        infos = []
        for index, move in enumerate(legal[:multipv]):
            infos.append({
                "score": chess.engine.PovScore(chess.engine.Cp(20 - index * 10), chess.WHITE),
                "pv": self._line(board, move),
            })
        return infos


class _SwingStubEngine(_StubEngine):
    def analyse(self, board, _limit, multipv=2):
        self.calls += 1
        cp = 300 if self.calls == 1 else -300
        legal = list(board.legal_moves)
        return [
            {
                "score": chess.engine.PovScore(
                    chess.engine.Cp(cp - index * 10), chess.WHITE
                ),
                "pv": self._line(board, move),
            }
            for index, move in enumerate(legal[:multipv])
        ]


def test_streaming_analysis_stays_serializable_without_extra_engine_calls():
    engine = _StubEngine()
    events = list(analyze_game_streaming("1. e4 e5", engine, depth=8))
    complete = next(payload for event, payload in events if event == "complete")

    assert engine.calls == 3  # initial position plus one existing search per ply
    assert len(complete["move_data"]) == 2
    json.dumps(complete)


def test_full_game_and_single_move_paths_expose_the_same_richer_facts():
    stream_engine = _SwingStubEngine()
    events = list(analyze_game_streaming("1. e4", stream_engine, depth=8))
    full_move = next(payload for event, payload in events if event == "complete")["move_data"][0]

    single_engine = _SwingStubEngine()
    single_move = analyze_move(chess.STARTING_FEN, "e2e4", single_engine, depth=8)

    for entry in (full_move, single_move):
        assert entry["classification"] == "Blunder"
        assert entry["facts"]["is_sacrifice"] is False
        assert len(entry["facts"]["forcing_line"]) >= 2
        assert len(entry["facts"]["best_line"]) >= 2
        assert entry["facts"]["refutation"]
    assert stream_engine.calls == 2
    assert single_engine.calls == 2

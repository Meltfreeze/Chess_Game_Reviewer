"""Verified coaching facts derived without additional engine searches."""

import json

import chess
import chess.engine

from backend.engine import (
    _history_capture_context,
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


class _GreatStubEngine(_StubEngine):
    def analyse(self, board, _limit, multipv=2):
        self.calls += 1
        if self.calls == 1:
            candidates = [
                (chess.Move.from_uci("e2e4"), 20),
                (chess.Move.from_uci("d2d4"), -150),
            ]
        else:
            candidates = [
                (move, 20 - index * 10)
                for index, move in enumerate(list(board.legal_moves)[:multipv])
            ]
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE),
                "pv": self._line(board, move),
            }
            for move, cp in candidates[:multipv]
        ]


class _BrilliantStubEngine(_StubEngine):
    fen = "4k3/4p3/8/8/8/8/8/4R1K1 w - - 0 1"

    def __init__(self, accept_main=True, forced_capture_cp=100):
        super().__init__()
        self.accept_main = accept_main
        self.forced_capture_cp = forced_capture_cp

    def analyse(self, board, _limit, multipv=2, root_moves=None):
        self.calls += 1
        sacrifice = chess.Move.from_uci("e1e7")
        capture = chess.Move.from_uci("e8e7")
        decline = chess.Move.from_uci("e8f8")

        if root_moves is not None:
            assert root_moves == [capture]
            return [{
                "score": chess.engine.PovScore(
                    chess.engine.Cp(self.forced_capture_cp), chess.WHITE
                ),
                "pv": _pv(board, "e8e7"),
            }]

        if board.turn == chess.WHITE:
            main_reply = "e8e7" if self.accept_main else "e8f8"
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(100), chess.WHITE),
                    "pv": _pv(board, "e1e7", main_reply),
                },
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(90), chess.WHITE),
                    "pv": _pv(board, "e1e2"),
                },
            ]

        reply = capture if self.accept_main else decline
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(100), chess.WHITE),
                "pv": self._line(board, reply),
            },
            {
                "score": chess.engine.PovScore(chess.engine.Cp(90), chess.WHITE),
                "pv": self._line(
                    board,
                    next(move for move in board.legal_moves if move != reply),
                ),
            },
        ][:multipv]


def test_streaming_analysis_stays_serializable_without_extra_engine_calls():
    engine = _StubEngine()
    events = list(analyze_game_streaming("1. e4 e5", engine, depth=8))
    complete = next(payload for event, payload in events if event == "complete")

    assert engine.calls == 3  # initial position plus one existing search per ply
    assert len(complete["move_data"]) == 2
    for entry in complete["move_data"]:
        assert entry["played_move"] == entry["uci"]
        assert entry["best_move"] == entry["best_uci"]
        assert 0.0 <= entry["best_wp"] <= 1.0
        assert 0.0 <= entry["second_best_wp"] <= 1.0
        assert entry["legal_move_count"] > 0
    json.dumps(complete)


def test_history_capture_context_requires_a_matching_replay():
    board = chess.Board()
    history = ["e2e4", "d7d5", "e4d5"]
    for uci in history:
        board.push_uci(uci)

    previous_move, was_capture = _history_capture_context(board, history)
    assert previous_move == chess.Move.from_uci("e4d5")
    assert was_capture

    mismatched = chess.Board()
    assert _history_capture_context(mismatched, history) == (None, False)


def test_single_move_pipeline_emits_great_and_root_analysis_fields():
    entry = analyze_move(chess.STARTING_FEN, "e2e4", _GreatStubEngine(), depth=8)

    assert entry["classification"] == "Great"
    assert entry["played_move"] == "e2e4"
    assert entry["best_move"] == "e2e4"
    assert entry["best_wp"] > entry["second_best_wp"]
    assert entry["legal_move_count"] == 20


def test_single_move_pipeline_reuses_main_pv_for_accepted_brilliant_sacrifice():
    engine = _BrilliantStubEngine(accept_main=True)
    entry = analyze_move(engine.fen, "e1e7", engine, depth=8)

    assert entry["classification"] == "Brilliant"
    assert entry["facts"]["is_sacrifice"] is True
    assert engine.calls == 2


def test_single_move_pipeline_verifies_declined_brilliant_with_one_extra_search():
    engine = _BrilliantStubEngine(accept_main=False, forced_capture_cp=100)
    entry = analyze_move(engine.fen, "e1e7", engine, depth=8)

    assert entry["classification"] == "Brilliant"
    assert entry["facts"]["is_sacrifice"] is True
    assert engine.calls == 3


def test_single_move_pipeline_rejects_sacrifice_refuted_by_forced_capture():
    engine = _BrilliantStubEngine(accept_main=False, forced_capture_cp=-500)
    entry = analyze_move(engine.fen, "e1e7", engine, depth=8)

    assert entry["classification"] == "Best"
    assert entry["facts"]["is_sacrifice"] is False
    assert engine.calls == 3


def test_full_game_and_single_move_paths_expose_the_same_richer_facts():
    stream_engine = _SwingStubEngine()
    events = list(analyze_game_streaming("1. e4", stream_engine, depth=8))
    full_move = next(payload for event, payload in events if event == "complete")["move_data"][0]

    single_engine = _SwingStubEngine()
    single_move = analyze_move(
        chess.STARTING_FEN,
        "e2e4",
        single_engine,
        depth=8,
        uci_history=[],
    )

    for entry in (full_move, single_move):
        assert entry["classification"] == "Blunder"
        assert entry["facts"]["is_sacrifice"] is False
        assert len(entry["facts"]["forcing_line"]) >= 2
        assert len(entry["facts"]["best_line"]) >= 2
        assert entry["facts"]["refutation"]
    assert full_move == single_move
    assert stream_engine.calls == 2
    assert single_engine.calls == 2

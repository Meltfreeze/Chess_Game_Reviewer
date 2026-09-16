"""Move-classification rules and their priority ordering.

The short-circuits are ranked on purpose, so these tests pin the ranking rather
than the thresholds: mate outranks everything, a book move is not graded at all,
and Miss only reaches moves the eval ladder would otherwise have let pass.
"""

import chess

from backend.engine import (
    classify_move,
    is_great,
    is_trivially_obvious,
    is_unique_best,
)

# prev/curr chosen so the eval ladder alone returns "Good" -- gentle enough that
# is_miss_move would be allowed to fire, and inside the |curr_cp| < 80 window
# that the caller requires before it will set is_book.
QUIET = {"prev_cp": 20, "curr_cp": -20, "is_great_move": False, "is_sac": False}


def test_ladder_alone_grades_the_fixture():
    """Documents what QUIET means, so the ordering tests below are readable."""
    assert classify_move(**QUIET, is_book=False) == "Good"


def test_book_outranks_miss():
    """Regression: 1. h4 is a named line and was coming back as Miss."""
    assert classify_move(**QUIET, is_book=True, is_miss=True) == "Book"


def test_miss_applies_when_the_move_is_not_book():
    assert classify_move(**QUIET, is_book=False, is_miss=True) == "Miss"


def test_book_outranks_the_eval_ladder():
    losing = {"prev_cp": 60, "curr_cp": -60, "is_great_move": False, "is_sac": False}
    assert classify_move(**losing, is_book=False) == "Mistake"
    assert classify_move(**losing, is_book=True) == "Book"


def test_mate_outranks_book_and_miss():
    assert classify_move(**QUIET, is_book=True, is_miss=True, is_mate=True) == "Best"


def test_mate_by_sacrifice_is_brilliant():
    sacked = {**QUIET, "is_sac": True}
    assert classify_move(**sacked, is_book=True, is_miss=True, is_mate=True) == "Brilliant"


def test_unique_best_accepts_large_absolute_gap():
    assert is_unique_best(0.52, 0.30)


def test_unique_best_accepts_large_relative_gap_in_bad_position():
    assert is_unique_best(0.18, 0.04)


def test_unique_best_rejects_similar_moves_in_bad_position():
    assert not is_unique_best(0.18, 0.14)


def test_unique_best_rejects_similar_moves_in_winning_position():
    assert not is_unique_best(0.92, 0.88)


def test_only_legal_move_is_never_great():
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")

    assert not is_great(move, move, 0.80, 0.10, 1, board)
    assert is_trivially_obvious(move, board, legal_move_count=1)


def test_great_requires_exact_best_move_identity():
    board = chess.Board()

    assert not is_great(
        chess.Move.from_uci("d2d4"),
        chess.Move.from_uci("e2e4"),
        0.80,
        0.10,
        board.legal_moves.count(),
        board,
    )


def _assert_obvious_move_stays_best(board, move, **context):
    legal_move_count = board.legal_moves.count()
    assert is_trivially_obvious(
        move, board, legal_move_count=legal_move_count, **context
    )
    great = is_great(
        move,
        move,
        0.52,
        0.30,
        legal_move_count,
        board,
        **context,
    )
    assert not great
    assert classify_move(0, 0, great, is_sac=False, is_book=False) == "Best"


def test_safe_same_square_recapture_is_obvious_and_stays_best():
    board = chess.Board()
    for uci in ("e2e4", "d7d5", "e4d5"):
        board.push_uci(uci)
    move = chess.Move.from_uci("d8d5")

    _assert_obvious_move_stays_best(
        board,
        move,
        previous_move=board.peek(),
        previous_move_was_capture=True,
    )


def test_safe_capture_of_undefended_queen_is_obvious_and_stays_best():
    board = chess.Board("4k3/8/8/8/8/8/4q3/4R1K1 w - - 0 1")
    _assert_obvious_move_stays_best(board, chess.Move.from_uci("e1e2"))


def test_safe_capture_of_undefended_rook_is_obvious_and_stays_best():
    board = chess.Board("4k3/8/8/8/8/8/4r3/4R1K1 w - - 0 1")
    _assert_obvious_move_stays_best(board, chess.Move.from_uci("e1e2"))


def test_safe_automatic_queen_promotion_is_obvious_and_stays_best():
    board = chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1")
    _assert_obvious_move_stays_best(board, chess.Move.from_uci("a7a8q"))


def test_queen_promotion_that_is_immediately_lost_is_not_obvious():
    board = chess.Board("1r5k/P7/8/8/8/8/8/7K w - - 0 1")

    assert not is_trivially_obvious(chess.Move.from_uci("a7a8q"), board)


def test_check_evasion_and_king_move_are_not_inherently_obvious():
    board = chess.Board("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")
    move = chess.Move.from_uci("e1f1")

    assert board.is_check()
    assert board.piece_at(move.from_square).piece_type == chess.KING
    assert not is_trivially_obvious(move, board)


def test_capture_and_checking_move_are_not_inherently_obvious():
    board = chess.Board("4k3/8/8/8/8/8/4p3/3KQ3 w - - 0 1")
    move = chess.Move.from_uci("e1e2")

    assert board.is_capture(move)
    assert board.gives_check(move)
    assert not is_trivially_obvious(move, board)


def test_brilliant_outranks_great():
    assert classify_move(
        prev_cp=0,
        curr_cp=0,
        is_great_move=True,
        is_sac=True,
        is_book=False,
    ) == "Brilliant"


def test_great_has_no_minimum_resulting_win_probability():
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    great = is_great(move, move, 0.18, 0.04, board.legal_moves.count(), board)

    assert great
    assert classify_move(
        prev_cp=-300,
        curr_cp=-300,
        is_great_move=great,
        is_sac=False,
        is_book=False,
    ) == "Great"

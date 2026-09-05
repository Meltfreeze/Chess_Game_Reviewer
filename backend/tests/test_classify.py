"""Ordering rules in classify_move.

The short-circuits are ranked on purpose, so these tests pin the ranking rather
than the thresholds: mate outranks everything, a book move is not graded at all,
and Miss only reaches moves the eval ladder would otherwise have let pass.
"""

from backend.engine import classify_move

# prev/curr chosen so the eval ladder alone returns "Good" -- gentle enough that
# is_miss_move would be allowed to fire, and inside the |curr_cp| < 80 window
# that the caller requires before it will set is_book.
QUIET = {"prev_cp": 20, "curr_cp": -20, "is_only_move": False, "is_sac": False}


def test_ladder_alone_grades_the_fixture():
    """Documents what QUIET means, so the ordering tests below are readable."""
    assert classify_move(**QUIET, is_book=False) == "Good"


def test_book_outranks_miss():
    """Regression: 1. h4 is a named line and was coming back as Miss."""
    assert classify_move(**QUIET, is_book=True, is_miss=True) == "Book"


def test_miss_applies_when_the_move_is_not_book():
    assert classify_move(**QUIET, is_book=False, is_miss=True) == "Miss"


def test_book_outranks_the_eval_ladder():
    losing = {"prev_cp": 60, "curr_cp": -60, "is_only_move": False, "is_sac": False}
    assert classify_move(**losing, is_book=False) == "Mistake"
    assert classify_move(**losing, is_book=True) == "Book"


def test_mate_outranks_book_and_miss():
    assert classify_move(**QUIET, is_book=True, is_miss=True, is_mate=True) == "Best"


def test_mate_by_sacrifice_is_brilliant():
    sacked = {**QUIET, "is_sac": True}
    assert classify_move(**sacked, is_book=True, is_miss=True, is_mate=True) == "Brilliant"

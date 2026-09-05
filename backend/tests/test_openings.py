"""Tests for the ECO opening table and the Book gate built on it.

These are engine-free: is_book_move and lookup_opening are pure functions over
the generated data/openings.tsv, so they run in milliseconds.
"""

from backend.openings import BOOK_MAX_PLIES, _OPENINGS, is_book_move, lookup_opening

# Ruy Lopez, Marshall Attack -- the dataset names this line out to 36 plies, so
# it runs well past BOOK_MAX_PLIES and exercises the cap.
MARSHALL = ("e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 f1e1 b7b5 "
            "a4b3 e8g8").split()

# The same opening through 5...Be7, then 6. g4 -- in no named line. The
# deviation sits at ply 10, inside the cap, so this tests table membership
# rather than the cap.
OFF_BOOK = "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 g2g4".split()


def test_table_is_fully_loaded():
    """Guards against a truncated or half-written regeneration."""
    assert len(_OPENINGS) > 3000


def test_opening_move_is_book():
    assert is_book_move([], "e2e4") is True


def test_book_follows_a_named_line():
    for ply in range(BOOK_MAX_PLIES):
        assert is_book_move(MARSHALL[:ply], MARSHALL[ply]) is True, f"ply {ply}"


def test_book_stops_at_the_cap():
    """The named line continues here; only BOOK_MAX_PLIES ends it."""
    ply = BOOK_MAX_PLIES
    assert ply < len(MARSHALL)
    assert is_book_move(MARSHALL[:ply], MARSHALL[ply]) is False


def test_leaving_the_named_line_is_not_book():
    ply = len(OFF_BOOK) - 1
    assert ply < BOOK_MAX_PLIES, "the cap must not be what fails this"
    assert is_book_move(OFF_BOOK[:ply], OFF_BOOK[ply]) is False


def test_book_is_closed_downward():
    """Once a path leaves the book, no extension of it comes back."""
    history = list(OFF_BOOK)
    for move in ("d2d4", "b1c3", "h2h3"):
        assert is_book_move(history, move) is False
        history.append(move)


def test_lookup_names_the_longest_matching_line():
    eco, name = lookup_opening(MARSHALL[:BOOK_MAX_PLIES])
    assert eco
    assert "Ruy Lopez" in name


def test_lookup_keeps_the_name_after_leaving_the_book():
    on_book = lookup_opening(OFF_BOOK[:-1])
    assert on_book != (None, None)
    assert lookup_opening(OFF_BOOK) == on_book


def test_lookup_of_the_start_position_is_unnamed():
    """Every one of the 20 legal first moves is named, so only [] is unknown."""
    assert lookup_opening([]) == (None, None)

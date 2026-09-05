"""ECO opening lookup backed by the lichess chess-openings dataset.

data/openings.tsv maps a UCI move sequence to its (ECO, name). It is generated
by tools/build_openings.py -- regenerate it rather than editing it by hand. A
missing data file raises at import on purpose: silently having no openings is
the failure mode this table exists to prevent.
"""

import csv
import os

BOOK_MAX_PLIES = 12
"""How far Book is allowed to run.

Named lines in the dataset reach 36 plies, but classify_move short-circuits on
Book before it grades anything, so an uncapped test would leave a player
following deep theory with no verdict on half their game.
"""

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "openings.tsv")


def _load(path=_DATA_PATH):
    """Return (lines, prefixes) -- exact-line lookup, plus every book prefix.

    Prefixes stop at BOOK_MAX_PLIES since is_book_move never asks about a
    longer path, which keeps the set to a fraction of its full size.
    """
    lines = {}
    prefixes = set()
    with open(path, encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if not row or row[0].startswith("#") or row[0] == "uci":
                continue
            uci, eco, name = row[0], row[1], row[2]
            lines[uci] = (eco, name)
            moves = uci.split(" ")
            for end in range(1, min(len(moves), BOOK_MAX_PLIES) + 1):
                prefixes.add(" ".join(moves[:end]))
    return lines, prefixes


_OPENINGS, _BOOK_PREFIXES = _load()


def lookup_opening(uci_moves):
    """Return (eco, name) for the longest named line prefixing these moves.

    The longest match stops growing once a game leaves the book, so the opening
    keeps its label for the rest of the game.
    """
    for end in range(len(uci_moves), 0, -1):
        info = _OPENINGS.get(" ".join(uci_moves[:end]))
        if info:
            return info
    return None, None


def is_book_move(uci_moves, uci):
    """True when playing `uci` from `uci_moves` stays inside a named opening line.

    `uci_moves` is the path from the starting position up to (not including)
    `uci`, so this answers "is the move itself still book". False once the line
    leaves every named opening, and False past BOOK_MAX_PLIES.
    """
    if len(uci_moves) >= BOOK_MAX_PLIES:
        return False
    return " ".join([*uci_moves, uci]) in _BOOK_PREFIXES

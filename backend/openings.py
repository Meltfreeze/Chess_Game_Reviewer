"""Lightweight ECO opening lookup by move sequence (UCI)."""

# Common opening lines: UCI move sequence -> (ECO code, name)
_OPENINGS = {
    "e2e4 e7e5 g1f3 b8c6 f1b5": ("C60", "Ruy Lopez"),
    "e2e4 e7e5 g1f3 b8c6 f1c4": ("C50", "Italian Game"),
    "e2e4 c7c5 g1f3 d7d6 d2d4": ("B50", "Sicilian Defense"),
    "e2e4 e7e6 d2d4 d7d5 b1c3": ("C02", "French Defense"),
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3": ("B90", "Sicilian Najdorf"),
    "d2d4 d7d5 c2c4": ("D06", "Queen's Gambit"),
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6": ("D42", "Queen's Gambit Declined"),
    "d2d4 g8f6 c2c4 g7g6 b1c3 d7d5": ("E60", "King's Indian Defense"),
    "e2e4 e7e5 g1f3 g8f6": ("C42", "Petrov Defense"),
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5": ("C51", "Italian Game: Evans Gambit"),
    "e2e4 c7c5 g1f3 b8c6 f1b5": ("B30", "Sicilian Defense"),
    "e2e4 e7e5 b1c3": ("C20", "King's Pawn Game"),
    "d2d4 g8f6 c2c4 e7e6 b1c3 f8b4": ("E20", "Nimzo-Indian Defense"),
    "d2d4 g8f6 c2c4 e7e6 g1f3 d7d5 b1c3 f8e7": ("E32", "Nimzo-Indian Defense"),
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4": ("C70", "Ruy Lopez: Morphy Defense"),
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3 g8f6": ("C54", "Italian Game: Giuoco Piano"),
    "e2e4 c7c5 g1f3 e7e6 d2d4 c5d4 f3d4": ("B40", "Sicilian Defense"),
    "e2e4 e7e5 g1f3 b8c6 f1b5 g8f6": ("C65", "Ruy Lopez: Berlin Defense"),
    "d2d4 d7d5 c2c4 d5c4 e2e4 g8f6": ("D20", "Queen's Gambit Accepted"),
    "g1f3 d7d5 d2d4": ("A40", "Queen's Pawn Game"),
}


def lookup_opening(uci_moves):
    """Return (eco, name) for the longest matching prefix of UCI moves."""
    key = " ".join(uci_moves)
    best = None
    for prefix, info in _OPENINGS.items():
        if key.startswith(prefix) or prefix.startswith(key):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, info)
    if best and key.startswith(best[0]):
        return best[1]
    # partial match on longest prefix contained in key
    for prefix, info in sorted(_OPENINGS.items(), key=lambda x: -len(x[0])):
        if key.startswith(prefix):
            return info
    return None, None


def is_book_move(uci_moves, ply):
    eco, name = lookup_opening(uci_moves)
    if eco and ply < len(uci_moves) + 2:
        return True, eco, name
    if ply < 8 and eco:
        return True, eco, name
    return False, eco, name

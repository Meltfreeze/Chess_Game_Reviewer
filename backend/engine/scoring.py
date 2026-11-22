"""Pure score conversion and accuracy helpers for chess analysis."""

import math


def cp_to_wp(cp):
    cp = max(-10000, min(10000, cp))
    return 1 / (1 + 10 ** (-cp / 400))


def _win_percent(cp):
    """Win expectancy 0-100 for the side that just moved.

    Kept separate from cp_to_wp on purpose: the accuracy curve below is
    calibrated against this sigmoid, while cp_to_wp feeds the classification
    thresholds and must not shift.
    """
    cp = max(-10000, min(10000, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def _move_accuracy(win_before, win_after):
    """Accuracy 0-100 for one move, from how much win expectancy it gave up."""
    drop = max(0.0, win_before - win_after)
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * drop) - 3.1669))


def _game_accuracy(per_move, win_seq):
    """Collapse per-move accuracies into one 0-100 figure for a player.

    Mean of a volatility-weighted mean and a harmonic mean: the weighting keeps
    quiet positions from drowning out sharp ones, and the harmonic mean stops a
    handful of terrible moves from being averaged away by many easy ones.
    """
    if not per_move:
        return 0.0
    window = max(2, min(8, len(per_move) // 10))
    weights = []
    for i in range(len(per_move)):
        seg = win_seq[max(0, i - window + 1):i + 1] or [50.0]
        mean = sum(seg) / len(seg)
        stdev = (sum((x - mean) ** 2 for x in seg) / len(seg)) ** 0.5
        weights.append(max(0.5, stdev))
    weighted = sum(a * w for a, w in zip(per_move, weights)) / sum(weights)
    harmonic = len(per_move) / sum(1.0 / max(a, 1.0) for a in per_move)
    return round((weighted + harmonic) / 2, 1)


def _score_white_cp(info):
    return info["score"].white().score(mate_score=10000)


def _eval_str(pov_white_score):
    if pov_white_score.is_mate():
        return f"#{pov_white_score.mate()}"
    return f"{pov_white_score.score() / 100:+.2f}"

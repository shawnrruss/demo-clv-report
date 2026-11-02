"""Decimal-odds helpers: no-vig fair probabilities and closing line value.

The no-vig method is the proportional (normalise the implied probabilities)
method: every side's implied probability is divided by the overround of the
whole market, so the fair probabilities of all sides sum to 1.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def implied_prob(odds: float) -> float:
    """Implied probability of a decimal price, overround included."""
    if not math.isfinite(odds) or odds <= 1.0:
        raise ValueError(f"decimal odds must be > 1, got {odds}")
    return 1.0 / odds


def fair_prob(closing_odds: float, other_odds: Sequence[float]) -> float:
    """No-vig closing probability of the back side of the market."""
    implied = [implied_prob(closing_odds)]
    implied.extend(implied_prob(odds) for odds in other_odds)
    return implied[0] / sum(implied)


def closing_line_value(taken_odds: float, fair_close_prob: float) -> float:
    """CLV = taken_odds * fair_close_prob - 1 (per unit staked)."""
    return taken_odds * fair_close_prob - 1.0

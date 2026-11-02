"""Seeded percentile bootstrap for ROI, mean CLV and fair-close ROI."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from operator import itemgetter


def percentile_interval(values: Sequence[float], level: float = 0.95) -> tuple[float, float]:
    """Percentile (p-) interval of a sample, symmetric in the tails."""
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        raise ValueError("cannot take an interval of an empty sample")
    tail = (1.0 - level) / 2.0
    low = ordered[max(0, math.floor(tail * count))]
    high = ordered[min(count - 1, math.ceil((1.0 - tail) * count) - 1)]
    return low, high


def bootstrap_intervals(
    rows: Sequence[tuple[float, float, float, float]],
    *,
    resamples: int,
    seed: int,
    level: float = 0.95,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Resample (profit, stake, clv, fair_profit) rows for all three intervals."""
    if resamples < 1:
        raise ValueError(f"resamples must be at least 1, got {resamples}")
    count = len(rows)
    if count == 0:
        raise ValueError("cannot bootstrap an empty sample")
    rng = random.Random(seed)
    randrange = rng.randrange
    profit_of = itemgetter(0)
    stake_of = itemgetter(1)
    clv_of = itemgetter(2)
    fair_profit_of = itemgetter(3)
    rois: list[float] = []
    clvs: list[float] = []
    fair_rois: list[float] = []
    for _ in range(resamples):
        sample = [rows[randrange(count)] for _ in range(count)]
        staked = sum(map(stake_of, sample))
        rois.append(sum(map(profit_of, sample)) / staked)
        clvs.append(sum(map(clv_of, sample)) / count)
        fair_rois.append(sum(map(fair_profit_of, sample)) / staked)
    return (
        percentile_interval(rois, level),
        percentile_interval(clvs, level),
        percentile_interval(fair_rois, level),
    )

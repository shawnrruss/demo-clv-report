"""Simulate a bets CSV: a calibrated closing market plus an optional true edge."""

from __future__ import annotations

import random
from datetime import date, timedelta

from clvreport.bets import Bet, build_bet
from clvreport.report import DEFAULT_SEED

MARGIN = 0.04
CLV_NOISE = 0.01
VOID_RATE = 0.02
MIN_PROB = 0.15
MAX_PROB = 0.85
START = date(2024, 1, 1)


def simulate_bets(n: int, *, edge: float = 0.0, seed: int = DEFAULT_SEED) -> list[Bet]:
    """Return n simulated bets.

    The closing market carries a fixed 4% proportional margin around a true
    probability, so the no-vig closing price is exactly fair (edge=0 means
    calibrated). Taken prices differ from the fair closing price by ``edge``
    plus 1% noise, and results are drawn from the true probability.
    """
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")
    rng = random.Random(seed)
    overround = 1.0 + MARGIN
    bets: list[Bet] = []
    for index in range(n):
        true_prob = rng.uniform(MIN_PROB, MAX_PROB)
        closing = round(1.0 / (true_prob * overround), 3)
        other = round(1.0 / ((1.0 - true_prob) * overround), 3)
        taken = round(max(1.01, (1.0 + edge + rng.gauss(0.0, CLV_NOISE)) / true_prob), 3)
        result = "win" if rng.random() < true_prob else "lose"
        if rng.random() < VOID_RATE:
            result = "void"
        bets.append(
            build_bet(
                date=(START + timedelta(days=index // 4)).isoformat(),
                event=f"Event {index + 1:03d}",
                selection="Side A" if index % 2 == 0 else "Side B",
                taken_odds=taken,
                closing_odds=closing,
                closing_odds_other=(other,),
                result=result,
                stake=1.00,
            )
        )
    return bets

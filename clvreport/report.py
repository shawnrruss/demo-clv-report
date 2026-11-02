"""Analysis of settled bets and the plain-text / JSON report."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean

from clvreport.bets import Bet
from clvreport.bootstrap import bootstrap_intervals

MIN_SETTLED = 30
RULE1_LIMIT = 0.015
DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 0
LEVEL = 0.95


@dataclass(frozen=True)
class Analysis:
    n_bets: int
    n_settled: int
    n_void: int
    staked: float
    profit: float
    roi: float
    mean_clv: float
    rule1_roi: float
    sufficient: bool
    roi_ci: tuple[float, float] | None
    clv_ci: tuple[float, float] | None
    rule1_ci: tuple[float, float] | None
    seed: int
    resamples: int

    @property
    def rule1_half_width(self) -> float | None:
        if self.rule1_ci is None:
            return None
        return (self.rule1_ci[1] - self.rule1_ci[0]) / 2.0

    @property
    def rule1_verdict(self) -> str | None:
        half_width = self.rule1_half_width
        if self.rule1_ci is None or half_width is None:
            return None
        if abs(self.rule1_roi) <= RULE1_LIMIT and half_width <= RULE1_LIMIT:
            return "PASS"
        low, high = self.rule1_ci
        if low > RULE1_LIMIT or high < -RULE1_LIMIT:
            return "FAIL"
        return "INCONCLUSIVE"

    @property
    def rule1_pass(self) -> bool | None:
        verdict = self.rule1_verdict
        if verdict is None or verdict == "INCONCLUSIVE":
            return None
        return verdict == "PASS"

    @property
    def rule1_message(self) -> str | None:
        if self.rule1_verdict != "INCONCLUSIVE":
            return None
        half_width = self.rule1_half_width
        if half_width is not None and half_width > RULE1_LIMIT:
            return (
                f"need more bets: interval +/-{half_width * 100:.2f} pt is wider than"
                f" the {RULE1_LIMIT * 100:g} pt limit"
            )
        return f"need more bets: interval overlaps the +/-{RULE1_LIMIT * 100:g} pt limit"

    @property
    def message(self) -> str | None:
        if self.sufficient:
            return None
        return f"not enough data ({self.n_settled} bets, need {MIN_SETTLED})"


def fair_close_roi(settled: Sequence[Bet]) -> float:
    """Rule 1: ROI had every settled bet been struck at the fair closing price."""
    staked = sum(bet.stake for bet in settled)
    if staked <= 0.0:
        return 0.0
    return sum(bet.fair_profit for bet in settled) / staked


def analyze(
    bets: Sequence[Bet],
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
) -> Analysis:
    settled = [bet for bet in bets if bet.settled]
    staked = sum(bet.stake for bet in settled)
    profit = sum(bet.profit for bet in settled)
    roi = profit / staked if staked > 0.0 else 0.0
    mean_clv = fmean(bet.clv for bet in settled) if settled else 0.0
    rule1 = fair_close_roi(settled)
    sufficient = len(settled) >= MIN_SETTLED
    roi_ci: tuple[float, float] | None = None
    clv_ci: tuple[float, float] | None = None
    rule1_ci: tuple[float, float] | None = None
    if sufficient:
        rows = [(bet.profit, bet.stake, bet.clv, bet.fair_profit) for bet in settled]
        roi_ci, clv_ci, rule1_ci = bootstrap_intervals(
            rows, resamples=resamples, seed=seed, level=LEVEL
        )
    return Analysis(
        n_bets=len(bets),
        n_settled=len(settled),
        n_void=len(bets) - len(settled),
        staked=staked,
        profit=profit,
        roi=roi,
        mean_clv=mean_clv,
        rule1_roi=rule1,
        sufficient=sufficient,
        roi_ci=roi_ci,
        clv_ci=clv_ci,
        rule1_ci=rule1_ci,
        seed=seed,
        resamples=resamples,
    )


def _pct(value: float) -> str:
    if abs(value) < 5e-5:
        value = 0.0
    return f"{value * 100:+.2f}%"


def _points(value: float) -> str:
    if abs(value) < 5e-5:
        value = 0.0
    return f"{value * 100:+.2f} pt"


def format_text(analysis: Analysis, out_csv: str | None = None) -> str:
    lines = [
        "CLV REPORT - simulated demo data, not betting advice",
        f"bets {analysis.n_bets}  settled {analysis.n_settled}  void {analysis.n_void}",
        f"staked {analysis.staked:.2f}  profit {analysis.profit:+.2f}"
        f"  ROI {_pct(analysis.roi)}",
        f"mean CLV {_pct(analysis.mean_clv)}",
        "",
    ]
    if not analysis.sufficient:
        lines.append(analysis.message or "")
        return "\n".join(lines)
    roi_ci, clv_ci, rule1_ci = analysis.roi_ci, analysis.clv_ci, analysis.rule1_ci
    if roi_ci is None or clv_ci is None or rule1_ci is None:
        raise ValueError("intervals missing for a sample of 30+ settled bets")
    lines.append(
        f"Rule 1 fair-close ROI {_points(analysis.rule1_roi)}  {analysis.rule1_verdict}"
        f" (limit +/-{RULE1_LIMIT * 100:.2f} pt)"
        f"  95% interval [{_points(rule1_ci[0])}, {_points(rule1_ci[1])}]"
    )
    if analysis.rule1_message:
        lines.append(analysis.rule1_message)
    lines.append("")
    lines.append(
        f"95% bootstrap intervals, {analysis.resamples} resamples, seed {analysis.seed}"
    )
    lines.append(f"  ROI      [{_pct(roi_ci[0])}, {_pct(roi_ci[1])}]")
    lines.append(f"  mean CLV [{_pct(clv_ci[0])}, {_pct(clv_ci[1])}]")
    if out_csv:
        lines.append("")
        lines.append(f"per-bet rows written to {out_csv}")
    return "\n".join(lines)


def as_dict(analysis: Analysis) -> dict[str, object]:
    roi_ci = analysis.roi_ci
    clv_ci = analysis.clv_ci
    rule1_ci = analysis.rule1_ci
    intervals = None
    rule1 = None
    if roi_ci is not None and clv_ci is not None and rule1_ci is not None:
        intervals = {
            "level": LEVEL,
            "resamples": analysis.resamples,
            "seed": analysis.seed,
            "roi": list(roi_ci),
            "mean_clv": list(clv_ci),
            "fair_close_roi": list(rule1_ci),
        }
        rule1 = {
            "fair_close_roi": analysis.rule1_roi,
            "limit": RULE1_LIMIT,
            "pass": analysis.rule1_pass,
            "verdict": analysis.rule1_verdict,
            "interval": list(rule1_ci),
            "half_width": analysis.rule1_half_width,
            "message": analysis.rule1_message,
        }
    return {
        "bets": analysis.n_bets,
        "settled": analysis.n_settled,
        "void": analysis.n_void,
        "staked": round(analysis.staked, 4),
        "profit": round(analysis.profit, 4),
        "roi": analysis.roi,
        "mean_clv": analysis.mean_clv,
        "sufficient": analysis.sufficient,
        "message": analysis.message,
        "rule1": rule1,
        "intervals": intervals,
    }


def format_json(analysis: Analysis, out_csv: str | None = None) -> str:
    payload = as_dict(analysis)
    if out_csv:
        payload["per_bet_csv"] = out_csv
    return json.dumps(payload, indent=2)

"""Bet records, CSV loading/validation and CSV writing."""

from __future__ import annotations

import csv
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from clvreport.odds import closing_line_value, fair_prob

COLUMNS = (
    "date",
    "event",
    "selection",
    "taken_odds",
    "closing_odds",
    "closing_odds_other",
    "result",
    "stake",
)
ANALYSIS_COLUMNS = (*COLUMNS, "fair_close_prob", "clv")
RESULTS = ("win", "lose", "void")


class BetDataError(ValueError):
    """Raised when an input CSV is missing columns or holds a bad row."""


@dataclass(frozen=True)
class Bet:
    date: str
    event: str
    selection: str
    taken_odds: float
    closing_odds: float
    closing_odds_other: tuple[float, ...]
    result: str
    stake: float
    fair_close_prob: float
    clv: float

    @property
    def settled(self) -> bool:
        return self.result != "void"

    @property
    def profit(self) -> float:
        if self.result == "win":
            return self.stake * (self.taken_odds - 1.0)
        if self.result == "lose":
            return -self.stake
        return 0.0

    @property
    def fair_profit(self) -> float:
        """Profit had the bet been struck at the fair closing price."""
        if self.result == "win":
            return self.stake * (1.0 / self.fair_close_prob - 1.0)
        if self.result == "lose":
            return -self.stake
        return 0.0


def build_bet(
    *,
    date: str,
    event: str,
    selection: str,
    taken_odds: float,
    closing_odds: float,
    closing_odds_other: Sequence[float],
    result: str,
    stake: float,
) -> Bet:
    """Assemble a bet, deriving the fair closing probability and its CLV."""
    others = tuple(closing_odds_other)
    fair = fair_prob(closing_odds, others)
    return Bet(
        date=date,
        event=event,
        selection=selection,
        taken_odds=taken_odds,
        closing_odds=closing_odds,
        closing_odds_other=others,
        result=result,
        stake=stake,
        fair_close_prob=fair,
        clv=closing_line_value(taken_odds, fair),
    )


def _odds(raw: str | None, name: str) -> float:
    text = (raw or "").strip()
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{name} must be a decimal odds value, got {text!r}") from None
    if not math.isfinite(value) or value <= 1.0:
        raise ValueError(f"{name} must be a decimal odds value > 1, got {text!r}")
    return value


def _stake(raw: str | None) -> float:
    text = (raw or "").strip()
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"stake must be a decimal value, got {text!r}") from None
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"stake must be > 0, got {text!r}")
    return value


def _other_odds(raw: str | None) -> tuple[float, ...]:
    parts = [part for part in (raw or "").split(";") if part.strip()]
    if not parts:
        raise ValueError("closing_odds_other needs at least one price")
    return tuple(_odds(part, "closing_odds_other") for part in parts)


def _bet_from_row(row: dict[str, str]) -> Bet:
    text_date = (row["date"] or "").strip()
    try:
        date.fromisoformat(text_date)
    except ValueError:
        raise ValueError(f"date must be YYYY-MM-DD, got {text_date!r}") from None
    event = (row["event"] or "").strip()
    selection = (row["selection"] or "").strip()
    if not event:
        raise ValueError("event must not be empty")
    if not selection:
        raise ValueError("selection must not be empty")
    result = (row["result"] or "").strip().lower()
    if result not in RESULTS:
        raise ValueError(f"result must be one of win/lose/void, got {row['result']!r}")
    return build_bet(
        date=text_date,
        event=event,
        selection=selection,
        taken_odds=_odds(row["taken_odds"], "taken_odds"),
        closing_odds=_odds(row["closing_odds"], "closing_odds"),
        closing_odds_other=_other_odds(row["closing_odds_other"]),
        result=result,
        stake=_stake(row["stake"]),
    )


def load_bets(path: str | Path) -> list[Bet]:
    """Read and validate a bets CSV, raising BetDataError with the line number."""
    source = Path(path)
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [name for name in COLUMNS if name not in header]
        if missing:
            raise BetDataError(f"{source}: missing column(s): {', '.join(missing)}")
        bets: list[Bet] = []
        for row in reader:
            try:
                bets.append(_bet_from_row(row))
            except ValueError as exc:
                raise BetDataError(f"{source}:{reader.line_num}: {exc}") from None
    if not bets:
        raise BetDataError(f"{source}: no bets found")
    return bets


def _row(bet: Bet, columns: Sequence[str]) -> list[str]:
    values = {
        "date": bet.date,
        "event": bet.event,
        "selection": bet.selection,
        "taken_odds": f"{bet.taken_odds:.3f}",
        "closing_odds": f"{bet.closing_odds:.3f}",
        "closing_odds_other": ";".join(f"{odds:.3f}" for odds in bet.closing_odds_other),
        "result": bet.result,
        "stake": f"{bet.stake:.2f}",
        "fair_close_prob": f"{bet.fair_close_prob:.6f}",
        "clv": f"{bet.clv:+.6f}",
    }
    return [values[column] for column in columns]


def _write(bets: Sequence[Bet], path: str | Path, columns: Sequence[str]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(_row(bet, columns) for bet in bets)


def write_input_csv(bets: Sequence[Bet], path: str | Path) -> None:
    """Write the eight input columns, so the file can be fed back to the CLI."""
    _write(bets, path, COLUMNS)


def write_analysis_csv(bets: Sequence[Bet], path: str | Path) -> None:
    """Write the input columns plus the per-bet fair closing probability and CLV."""
    _write(bets, path, ANALYSIS_COLUMNS)

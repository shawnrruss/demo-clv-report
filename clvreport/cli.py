"""Command line interface: ``clvreport report`` and ``clvreport simulate``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from clvreport.bets import load_bets, write_analysis_csv, write_input_csv
from clvreport.report import (
    DEFAULT_RESAMPLES,
    DEFAULT_SEED,
    analyze,
    format_json,
    format_text,
)
from clvreport.simulate import simulate_bets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clvreport",
        description="Closing line value report for a CSV of placed bets (analysis only).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    report = commands.add_parser("report", help="analyse a bets CSV")
    report.add_argument("input_csv", help="bets CSV to read")
    report.add_argument("--csv", dest="out_csv", metavar="OUT.csv", help="write per-bet rows")
    report.add_argument("--json", action="store_true", help="machine-readable output")
    report.add_argument("--seed", type=int, default=DEFAULT_SEED, help="bootstrap seed")
    report.add_argument(
        "--resamples",
        type=int,
        default=DEFAULT_RESAMPLES,
        help=f"bootstrap resamples (default {DEFAULT_RESAMPLES})",
    )

    simulate = commands.add_parser("simulate", help="write a simulated bets CSV")
    simulate.add_argument("--n", type=int, default=500, help="number of bets")
    simulate.add_argument("--edge", type=float, default=0.0, help="true edge, e.g. 0.03")
    simulate.add_argument("--seed", type=int, default=DEFAULT_SEED, help="simulation seed")
    simulate.add_argument("--out", required=True, help="CSV to write")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "simulate":
            bets = simulate_bets(args.n, edge=args.edge, seed=args.seed)
            write_input_csv(bets, args.out)
            print(
                f"wrote {len(bets)} simulated bets to {args.out}"
                f" (edge {args.edge * 100:+.2f}%, seed {args.seed})"
            )
            return 0
        bets = load_bets(args.input_csv)
        analysis = analyze(bets, seed=args.seed, resamples=args.resamples)
        if args.out_csv:
            write_analysis_csv(bets, args.out_csv)
        formatter = format_json if args.json else format_text
        print(formatter(analysis, args.out_csv))
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

import tempfile
import unittest
from pathlib import Path

from clvreport.bets import load_bets
from clvreport.cli import main


class CliTest(unittest.TestCase):
    def test_simulate_then_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sim.csv"
            out = Path(tmp) / "out.csv"
            code = main(["simulate", "--n", "40", "--seed", "1", "--out", str(source)])
            self.assertEqual(code, 0)
            self.assertEqual(len(load_bets(source)), 40)
            self.assertEqual(
                main(
                    [
                        "report",
                        str(source),
                        "--csv",
                        str(out),
                        "--resamples",
                        "20",
                        "--seed",
                        "1",
                    ]
                ),
                0,
            )
            rows = out.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 41)
            self.assertTrue(rows[0].endswith("fair_close_prob,clv"))

    def test_report_on_a_missing_file_exits_with_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["report", str(Path(tmp) / "nope.csv")]), 2)


if __name__ == "__main__":
    unittest.main()

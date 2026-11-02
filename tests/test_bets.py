import tempfile
import unittest
from pathlib import Path

from clvreport.bets import COLUMNS, BetDataError, load_bets, write_input_csv
from clvreport.report import analyze
from clvreport.simulate import simulate_bets

HEADER = ",".join(COLUMNS)


def _row(result="win", taken="2.000", stake="1.00"):
    return f"2024-01-01,Event 001,Side A,{taken},1.900,2.100,{result},{stake}"


class BetsCsvTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _file(self, *rows, header=HEADER, name="bets.csv"):
        path = self.dir / name
        path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
        return path

    def test_row_carries_fair_probability_and_clv(self):
        bet = load_bets(self._file(_row()))[0]
        self.assertAlmostEqual(bet.fair_close_prob, 0.525, places=12)
        self.assertAlmostEqual(bet.clv, 0.05, places=12)
        self.assertAlmostEqual(bet.profit, 1.00, places=12)

    def test_void_bets_are_excluded_from_roi(self):
        voids = [_row(result="void", taken="10.000", stake="5.00")] * 2
        rows = [_row() for _ in range(30)] + voids
        analysis = analyze(load_bets(self._file(*rows)), resamples=20, seed=1)
        self.assertEqual((analysis.n_bets, analysis.n_settled, analysis.n_void), (32, 30, 2))
        self.assertAlmostEqual(analysis.staked, 30.0, places=12)
        self.assertAlmostEqual(analysis.profit, 30.0, places=12)
        self.assertAlmostEqual(analysis.roi, 1.0, places=12)
        self.assertAlmostEqual(analysis.mean_clv, 0.05, places=12)
        self.assertAlmostEqual(analysis.rule1_roi, 1.0 / 0.525 - 1.0, places=12)

    def test_bad_rows_raise_clear_errors(self):
        cases = {
            "taken_odds": (
                _row(taken="abc"),
                ["taken_odds", "'abc'"],
            ),
            "result": (
                _row(result="push"),
                ["result must be one of win/lose/void", "'push'"],
            ),
            "date": (
                "01/01/2024,Event 001,Side A,2.000,1.900,2.100,win,1.00",
                ["date must be YYYY-MM-DD", "'01/01/2024'"],
            ),
            "stake": (
                _row(stake="0"),
                ["stake must be > 0"],
            ),
            "other_odds": (
                "2024-01-01,Event 001,Side A,2.000,1.900,,win,1.00",
                ["closing_odds_other"],
            ),
        }
        for name, (row, expected) in cases.items():
            with self.subTest(field=name):
                path = self._file(row, name=f"{name}.csv")
                with self.assertRaises(BetDataError) as caught:
                    load_bets(path)
                message = str(caught.exception)
                self.assertIn(f"{path.name}:2:", message)
                for fragment in expected:
                    self.assertIn(fragment, message)

    def test_missing_column_is_reported(self):
        path = self._file(
            "2024-01-01,Event 001,Side A,2.000,1.900,2.100,win",
            header=",".join(COLUMNS[:-1]),
        )
        with self.assertRaises(BetDataError) as caught:
            load_bets(path)
        self.assertIn("missing column(s): stake", str(caught.exception))

    def test_input_csv_round_trip(self):
        bets = simulate_bets(40, seed=4)
        path = self.dir / "sim.csv"
        write_input_csv(bets, path)
        reloaded = load_bets(path)
        self.assertEqual(len(reloaded), len(bets))
        for written, back in zip(bets, reloaded, strict=True):
            self.assertAlmostEqual(written.clv, back.clv, places=6)
            self.assertAlmostEqual(written.fair_close_prob, back.fair_close_prob, places=6)


if __name__ == "__main__":
    unittest.main()

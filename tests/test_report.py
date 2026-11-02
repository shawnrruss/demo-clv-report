import json
import unittest
from dataclasses import replace

from clvreport.report import MIN_SETTLED, RULE1_LIMIT, analyze, format_json, format_text
from clvreport.simulate import simulate_bets


class CalibratedMarketTest(unittest.TestCase):
    def test_calibrated_market_passes_rule1(self):
        bets = simulate_bets(40_000, edge=0.0, seed=1)
        analysis = analyze(bets, resamples=300, seed=0)
        self.assertTrue(analysis.sufficient)
        self.assertLess(abs(analysis.rule1_roi), RULE1_LIMIT)
        self.assertTrue(analysis.rule1_pass)
        self.assertLessEqual(analysis.rule1_half_width, RULE1_LIMIT)
        self.assertEqual(analysis.rule1_verdict, "PASS")
        self.assertIn("PASS", format_text(analysis))

    def test_500_calibrated_bets_are_inconclusive_and_reproducible(self):
        bets = simulate_bets(500, edge=0.0, seed=1)
        analysis = analyze(bets, resamples=400, seed=0)
        self.assertEqual(analysis, analyze(bets, resamples=400, seed=0))
        self.assertGreater(abs(analysis.rule1_roi), RULE1_LIMIT)
        self.assertGreater(analysis.rule1_half_width, RULE1_LIMIT)
        self.assertEqual(analysis.rule1_verdict, "INCONCLUSIVE")
        self.assertIsNone(analysis.rule1_pass)
        text = format_text(analysis)
        self.assertIn("INCONCLUSIVE", text)
        self.assertNotIn("FAIL", text)
        self.assertIn("need more bets: interval +/-", text)
        self.assertIn("is wider than the 1.5 pt limit", text)
        payload = json.loads(format_json(analysis))
        self.assertEqual(payload["rule1"]["verdict"], "INCONCLUSIVE")
        self.assertIsNone(payload["rule1"]["pass"])
        self.assertEqual(payload["rule1"]["message"], analysis.rule1_message)

    def test_strong_bias_fails_in_either_direction(self):
        bets = simulate_bets(4000, seed=1)
        for result in ("win", "lose"):
            with self.subTest(result=result):
                biased = [replace(bet, result=result) for bet in bets]
                analysis = analyze(biased, resamples=200, seed=0)
                self.assertEqual(analysis.rule1_verdict, "FAIL")
                self.assertFalse(analysis.rule1_pass)
                low, high = analysis.rule1_ci
                self.assertTrue(low > RULE1_LIMIT or high < -RULE1_LIMIT)
                self.assertIsNone(analysis.rule1_message)
                self.assertIn("FAIL", format_text(analysis))
                self.assertEqual(json.loads(format_json(analysis))["rule1"]["verdict"], "FAIL")

    def test_verdict_boundaries_and_narrow_overlap(self):
        base = analyze(simulate_bets(40, seed=1), resamples=20, seed=0)
        cases = (
            (0.0, (-RULE1_LIMIT, RULE1_LIMIT), "PASS"),
            (RULE1_LIMIT, (0.0, RULE1_LIMIT * 2), "PASS"),
            (-RULE1_LIMIT, (-RULE1_LIMIT * 2, 0.0), "PASS"),
            (0.0, (-0.02, 0.02), "INCONCLUSIVE"),
            (0.02, (RULE1_LIMIT, 0.025), "INCONCLUSIVE"),
            (-0.02, (-0.025, -RULE1_LIMIT), "INCONCLUSIVE"),
            (0.03, (0.02, 0.04), "FAIL"),
            (-0.03, (-0.04, -0.02), "FAIL"),
        )
        for roi, interval, verdict in cases:
            with self.subTest(roi=roi, interval=interval):
                analysis = replace(base, rule1_roi=roi, rule1_ci=interval)
                self.assertEqual(analysis.rule1_verdict, verdict)
        overlap = replace(base, rule1_roi=0.02, rule1_ci=(0.01, 0.03))
        self.assertEqual(overlap.rule1_verdict, "INCONCLUSIVE")
        self.assertEqual(
            overlap.rule1_message, "need more bets: interval overlaps the +/-1.5 pt limit"
        )

    def test_fair_roi_bootstrap_uses_stakes_and_excludes_voids(self):
        bets = [
            replace(
                bet,
                taken_odds=1.0 / bet.fair_close_prob,
                stake=index + 1.0,
            )
            for index, bet in enumerate(simulate_bets(100, seed=1))
        ]
        analysis = analyze(bets, resamples=100, seed=7)
        settled = analyze([bet for bet in bets if bet.settled], resamples=100, seed=7)
        self.assertEqual(analysis.rule1_roi, analysis.roi)
        self.assertEqual(analysis.rule1_ci, analysis.roi_ci)
        self.assertEqual(analysis.rule1_ci, settled.rule1_ci)


class InjectedEdgeTest(unittest.TestCase):
    def test_three_percent_edge_gives_positive_mean_clv_interval(self):
        analysis = analyze(simulate_bets(2000, edge=0.03, seed=7), resamples=400, seed=5)
        clv_ci = analysis.clv_ci
        if clv_ci is None:
            self.fail("expected a mean CLV interval for 2000 settled bets")
        self.assertGreater(clv_ci[0], 0.0)
        self.assertAlmostEqual(analysis.mean_clv, 0.03, delta=0.002)


class SmallSampleTest(unittest.TestCase):
    def test_29_settled_bets_print_not_enough_data(self):
        settled = [bet for bet in simulate_bets(80, seed=3) if bet.settled][:29]
        analysis = analyze(settled, resamples=50, seed=0)
        self.assertEqual(analysis.n_settled, MIN_SETTLED - 1)
        self.assertFalse(analysis.sufficient)
        self.assertIsNone(analysis.roi_ci)
        self.assertIsNone(analysis.clv_ci)
        self.assertIsNone(analysis.rule1_ci)
        self.assertIsNone(analysis.rule1_verdict)
        self.assertIsNone(analysis.rule1_pass)
        text = format_text(analysis)
        self.assertIn("not enough data (29 bets, need 30)", text)
        self.assertNotIn("Rule 1", text)
        self.assertNotIn("bootstrap intervals", text)
        payload = json.loads(format_json(analysis))
        self.assertIsNone(payload["rule1"])
        self.assertIsNone(payload["intervals"])
        self.assertEqual(payload["message"], "not enough data (29 bets, need 30)")


class ReportFormatTest(unittest.TestCase):
    def test_text_report(self):
        analysis = analyze(simulate_bets(120, seed=2), resamples=60, seed=1)
        text = format_text(analysis, "out.csv")
        self.assertIn("Rule 1 fair-close ROI", text)
        self.assertIn("(limit +/-1.50 pt)", text)
        self.assertIn(analysis.rule1_verdict, text)
        self.assertIn("95% interval [", text)
        self.assertIn("95% bootstrap intervals, 60 resamples, seed 1", text)
        self.assertIn("per-bet rows written to out.csv", text)

    def test_json_report(self):
        analysis = analyze(simulate_bets(120, seed=2), resamples=60, seed=1)
        payload = json.loads(format_json(analysis))
        self.assertEqual(payload["intervals"]["resamples"], 60)
        self.assertEqual(payload["intervals"]["seed"], 1)
        self.assertEqual(payload["intervals"]["level"], 0.95)
        self.assertEqual(payload["rule1"]["interval"], list(analysis.rule1_ci))
        self.assertEqual(payload["intervals"]["fair_close_roi"], list(analysis.rule1_ci))
        self.assertEqual(payload["rule1"]["half_width"], analysis.rule1_half_width)
        self.assertEqual(payload["rule1"]["limit"], RULE1_LIMIT)
        self.assertEqual(payload["rule1"]["verdict"], analysis.rule1_verdict)
        roi_low, roi_high = payload["intervals"]["roi"]
        self.assertLessEqual(roi_low, analysis.roi)
        self.assertGreaterEqual(roi_high, analysis.roi)


if __name__ == "__main__":
    unittest.main()

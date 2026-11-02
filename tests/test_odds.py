import unittest

from clvreport.odds import closing_line_value, fair_prob, implied_prob


class TwoWayNoVigTest(unittest.TestCase):
    """1.90 / 2.10 carries a 0.2506% overround: fair probs 52.5% and 47.5%."""

    def test_overround_and_fair_probability(self):
        self.assertAlmostEqual(implied_prob(1.9) + implied_prob(2.1), 1.0025062656641604, places=12)
        self.assertAlmostEqual(fair_prob(1.9, [2.1]), 0.525, places=12)
        self.assertAlmostEqual(fair_prob(2.1, [1.9]), 0.475, places=12)

    def test_closing_line_value(self):
        fair = fair_prob(1.9, [2.1])
        self.assertAlmostEqual(closing_line_value(2.0, fair), 0.05, places=12)
        self.assertAlmostEqual(closing_line_value(1.9, fair), -0.0025, places=12)


class ThreeWayNoVigTest(unittest.TestCase):
    """1.90 / 3.80 / 3.80: implied 0.52632 + 0.26316 + 0.26316 = 1.05263."""

    def test_fair_probabilities_sum_to_one(self):
        self.assertAlmostEqual(fair_prob(1.9, [3.8, 3.8]), 0.5, places=12)
        self.assertAlmostEqual(fair_prob(3.8, [1.9, 3.8]), 0.25, places=12)
        self.assertAlmostEqual(fair_prob(3.8, [1.9, 3.8]) * 2 + fair_prob(1.9, [3.8, 3.8]), 1.0)

    def test_closing_line_value(self):
        fair = fair_prob(1.9, [3.8, 3.8])
        self.assertAlmostEqual(closing_line_value(2.1, fair), 0.05, places=12)


class BadOddsTest(unittest.TestCase):
    def test_odds_at_or_below_one_are_rejected(self):
        for odds in (1.0, 0.5, -2.0, float("inf")):
            with self.subTest(odds=odds), self.assertRaises(ValueError):
                implied_prob(odds)


if __name__ == "__main__":
    unittest.main()

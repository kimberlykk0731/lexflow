"""Deterministic labour calculators."""
import unittest

from lexflow import rules


class TestCalculators(unittest.TestCase):
    def test_overtime(self):
        calc = rules.calculate_overtime(15000, weekday_h=10, rest_h=8, holiday_h=3)
        hourly = 15000 / 174
        self.assertAlmostEqual(calc["amount"],
                               round(hourly * (10 * 1.5 + 8 * 2 + 3 * 3), 2), places=1)

    def test_double_pay_capped(self):
        self.assertEqual(rules.calculate_double_wage(10000, 15)["months"], 11)
        self.assertEqual(rules.calculate_double_wage(10000, 15)["amount"], 110000)

    def test_annual_leave_extra_200(self):
        calc = rules.calculate_annual_leave(21750, 5)
        self.assertAlmostEqual(calc["amount"], 10000.0, places=2)
        self.assertAlmostEqual(calc["total_300"], 15000.0, places=2)

    def test_noncompete_30_percent(self):
        calc = rules.calculate_noncompete(20000, 12)
        self.assertEqual(calc["monthly"], 6000.0)
        self.assertEqual(calc["amount"], 72000.0)

    def test_work_injury_level_10(self):
        calc = rules.calculate_work_injury(10000, 10)
        self.assertEqual(calc["months"], 7)
        self.assertEqual(calc["amount"], 70000.0)

    def test_work_injury_unknown_level(self):
        self.assertFalse(rules.calculate_work_injury(10000, None)["ok"])


if __name__ == "__main__":
    unittest.main()

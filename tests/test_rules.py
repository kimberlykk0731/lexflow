"""Unit tests for the deterministic legal layer. Run:

    PYTHONPATH=src python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from lexflow.extract import find_correction_date
from lexflow.memory import CaseState
from lexflow.rules import (assess_dismissal, check_limitation,
                           compute_compensation, work_years, _tort_interp_version)
from lexflow.verify import Verifier
from lexflow.corpus import StatuteCorpus
from lexflow.rules import Analysis, Finding


class TestWorkYears(unittest.TestCase):
    def test_full_years(self):
        r = work_years("2018-03-01", "2026-01-10")
        self.assertEqual((r["years"], r["extra_months"], r["n"]), (7, 10, 8))

    def test_half_month(self):
        r = work_years("2020-01-01", "2020-06-30")
        self.assertEqual(r["n"], 0.5)

    def test_six_months_rounds_up(self):
        r = work_years("2020-01-01", "2020-07-01")
        self.assertEqual(r["n"], 1)

    def test_three_years_seven_months(self):
        r = work_years("2022-08-01", "2026-03-15")
        self.assertEqual(r["n"], 4)

    def test_invalid_dates(self):
        self.assertFalse(work_years("2026-01-01", "2025-01-01")["ok"])


class TestCompensation(unittest.TestCase):
    facts = {"start_date": "2021-05-01", "dismiss_date": "2026-03-15",
             "monthly_wage": 15000.0}

    def test_2n(self):
        r = compute_compensation(self.facts, pay_type="2N")
        self.assertTrue(r["ok"])
        self.assertEqual(r["amount"], 150000.0)

    def test_n(self):
        r = compute_compensation(self.facts, pay_type="N")
        self.assertEqual(r["amount"], 75000.0)

    def test_zero(self):
        r = compute_compensation(self.facts, pay_type="0")
        self.assertEqual(r["amount"], 0.0)

    def test_n_plus_one(self):
        r = compute_compensation(self.facts, pay_type="N", extra_notice=True)
        self.assertEqual(r["amount"], 90000.0)

    def test_missing_wage(self):
        r = compute_compensation({"start_date": "2021-05-01", "dismiss_date": "2026-03-15"},
                                 pay_type="N")
        self.assertFalse(r["ok"])


class TestLimitation(unittest.TestCase):
    def test_labor_one_year(self):
        r = check_limitation("labor_dismissal", "2026-03-15", "2026-11-18")
        self.assertEqual(r["deadline"], "2027-03-15")
        self.assertFalse(r["expired"])
        self.assertIn("labor_dispute", r["basis"])

    def test_labor_pre_2008_sixty_days(self):
        r = check_limitation("labor_dismissal", "2007-01-01", "2008-01-01")
        self.assertEqual(r["basis"], "labor_law@1995-01-01:第82条")
        self.assertEqual(r["deadline"], "2007-03-02")

    def test_tort_2016_one_year(self):
        r = check_limitation("tort_injury", "2016-01-01", "2016-06-01")
        self.assertEqual(r["basis"], "general_principles_civil_law@1987-01-01:第136条")
        self.assertEqual(r["deadline"], "2017-01-01")

    def test_tort_2018_three_years(self):
        r = check_limitation("tort_injury", "2018-01-01", "2018-02-01")
        self.assertEqual(r["basis"], "civil_general_principles@2017-10-01:第188条")
        self.assertEqual(r["deadline"], "2021-01-01")

    def test_tort_2022_civil_code(self):
        r = check_limitation("tort_injury", "2022-01-01", "2022-02-01")
        self.assertEqual(r["basis"], "civil_code_general@2021-01-01:第188条")


class TestVersionSelection(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(_tort_interp_version("2020-06-01")[0], "tort_interp_2003")
        self.assertEqual(_tort_interp_version("2021-06-01")[0], "tort_interp_2020")
        self.assertEqual(_tort_interp_version("2022-05-01")[0], "tort_interp_2022")


class TestDismissal(unittest.TestCase):
    def test_illegal_when_not_publicized(self):
        facts = {"who_initiated": "单位单方解除", "stated_reason": "严重违纪",
                 "rule_publicized": "没有公示告知", "rule_exists": "有成文制度",
                 "misconduct_proof": "只有口头指认", "union_notified": "没有通知",
                 "dismiss_date": "2026-03-15", "start_date": "2021-05-01",
                 "monthly_wage": 15000.0, "claim_type": "要求赔偿金"}
        a = assess_dismissal(facts, today="2026-11-18")
        self.assertTrue(a.metadata["illegal"])
        self.assertEqual(a.metadata["compensation"]["amount"], 150000.0)

    def test_lawful_no_compensation(self):
        facts = {"who_initiated": "单位单方解除", "stated_reason": "严重违纪",
                 "rule_publicized": "有签收或公示", "rule_exists": "有成文制度",
                 "rule_democratic": "经过了民主程序", "misconduct_proof": "有书面证据",
                 "union_notified": "已通知工会", "dismiss_date": "2026-01-10",
                 "start_date": "2018-03-01", "monthly_wage": 12000.0,
                 "claim_type": "要求赔偿金"}
        a = assess_dismissal(facts, today="2026-11-18")
        self.assertFalse(a.metadata["illegal"])
        self.assertEqual(a.metadata["compensation"]["amount"], 0.0)


class TestCorrectionDate(unittest.TestCase):
    def test_negated_then_corrected(self):
        self.assertEqual(find_correction_date("事故不是2023年6月，是2022年3月1日"),
                         "2022-03-01")

    def test_corrected_then_negated(self):
        self.assertEqual(find_correction_date("解除通知是2026年2月1日发的，不是2025年8月"),
                         "2026-02-01")


class TestVerifier(unittest.TestCase):
    def test_unknown_source(self):
        corpus = StatuteCorpus()
        state = CaseState(session="t")
        analysis = Analysis(case_type="labor_dismissal", as_of="2026-03-15",
                            headline="x", findings=[Finding(
                                id="F1", issue="x", conclusion="x", reasoning="x",
                                cites=["labor_contract@2008-01-01:第999条"])],
                            gaps=[], assumptions=[])
        result = Verifier(corpus).verify(analysis, state)
        self.assertEqual(result["support_rate"], 0.0)
        self.assertIn("UNKNOWN_SOURCE", [d["code"] for d in result["defects"]])


if __name__ == "__main__":
    unittest.main()

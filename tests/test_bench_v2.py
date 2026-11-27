"""Adversarial checks for scoring errors that would otherwise inflate results."""
import copy
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from api_audit import AuditedLLM
from gen_cases import build_cases
from metrics_v2 import (MISSING, active_facts, equal_value, fact_scores, question_scores,
                        revision_score, score_assertions)
from reference_oracle import add_year, compensated_months, reference_gold
from validate_cases import validate
from lexflow.agent import ConsultationAgent
from lexflow.config import Budget, LLMConfig
from lexflow.corpus import StatuteCorpus
from lexflow.elements import ElementSchema
from lexflow.extract import Extractor
from lexflow.llm import BaseLLM, LLMResult, NullLLM, build_llm
from lexflow.memory import MemoryStore
from lexflow.rules import analyse_many, compute_compensation, work_years


class TestBenchScoring(unittest.TestCase):
    def test_nonempty_wrong_fact_is_not_coverage(self):
        s = fact_scores({"salary": 9999}, {"salary": 12000}, {"salary": 12000}, ["salary"])
        self.assertEqual(s["correct_coverage"], 0)
        self.assertEqual(s["extraction_precision"], 0)

    def test_unasked_hidden_fact_is_not_credited(self):
        s = fact_scores({"salary": 12000}, {}, {"salary": 12000}, ["salary"])
        self.assertEqual(s["correct_coverage"], 0)
        self.assertEqual(s["incorrect_or_unsupported_keys"], ["salary"])

    def test_zero_is_known_but_missing_is_not_false(self):
        self.assertTrue(equal_value(0, 0))
        for value in (MISSING, None, 0, "false"):
            self.assertFalse(equal_value(value, False))
        self.assertTrue(equal_value(False, False))

    def test_per_claim_not_top_level(self):
        a = {"metadata": {"compensation": {"amount": 999}, "per_claim": {
            "a": {"calculation": {"amount": 120}}, "b": {"calculation": {"amount": 240}}}}}
        gold = [{"claim": c, "path": "calculation.amount", "expected": n, "applicable": True}
                for c, n in (("a", 120), ("b", 240))]
        self.assertTrue(all(r["ok"] for r in score_assertions(a, gold)))

    def test_repeated_questions_count_and_fixed_denominator(self):
        s = question_scores(["salary", "salary", "date"], ["salary", "date", "reason"], {"reason": "x"})
        self.assertEqual((s["questions"], s["unique_questions"], s["repeat_questions"]), (3, 2, 1))
        self.assertEqual(s["inquiry_recall"], 1)

    def test_amount_only_stale_revision_is_detected(self):
        before = {"case_type": "a", "metadata": {"calculation": {"amount": 100}}}
        gold = [{"claim": "a", "path": "calculation.amount", "expected": 200,
                 "applicable": True, "depends": ["salary"]}]
        s = revision_score(before, before, gold, {"salary": 200}, {"salary": 200}, {"salary": 200})
        self.assertTrue(s["corrected_facts_ok"])
        self.assertFalse(s["affected_outcomes_ok"])

    def test_unknown_and_superseded_are_excluded(self):
        self.assertEqual(active_facts([{"key": "a", "value": 1, "superseded_by": 2},
                                       {"key": "b", "value": "不清楚", "status": "unknown"},
                                       {"key": "c", "value": 0}]), {"c": 0})


class TestIndependentReference(unittest.TestCase):
    def test_positive_submonth_remainder(self):
        self.assertEqual(compensated_months("2026-03-01", "2026-03-15"), 0.5)
        self.assertEqual(compensated_months("2021-03-01", "2026-03-15"), 5.5)
        self.assertEqual(compensated_months("2021-03-01", "2026-03-01"), 5)

    def test_calendar_six_month_boundary_and_leap_day(self):
        self.assertEqual(compensated_months("2025-01-01", "2025-06-30"), 0.5)
        self.assertEqual(compensated_months("2025-01-01", "2025-07-01"), 1)
        self.assertEqual(add_year("2024-02-29"), "2025-02-28")

    def test_production_calculator_cannot_change_gold(self):
        case = {"reference_specs": [{"claim": "x", "path": "calculation.amount", "calculator": "double_pay",
                                     "depends": ["monthly_wage", "no_contract_months"]}]}
        with patch("lexflow.rules.calculate_double_wage", return_value={"amount": -999}):
            self.assertEqual(reference_gold(case, {"monthly_wage": 10000, "no_contract_months": 5}, "2026-11-27")[0]["expected"], 50000)

    def test_behavior_condition_is_not_a_formula_score(self):
        c = {"reference_specs": [{"claim": "x", "path": "finding:F_X", "calculator": "condition",
                                  "conditions": {"flag": "yes"}, "depends": ["flag"]}]}
        self.assertEqual(reference_gold(c, {"flag": "yes"}, "2026-11-27")[0]["reference_kind"], "author_specified_behavior")


class TestDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build_cases()
        cls.schema = ElementSchema().raw

    def test_counts_and_conditional_sides(self):
        r = validate(self.data, self.schema)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["n_cases"], 38)
        self.assertEqual(r["both_sides_covered"], r["conditional_fields"])
        self.assertEqual(r["tags"]["multi_claim"], 8)
        self.assertEqual(r["tags"]["unavailable_fact"], 6)
        self.assertEqual(r["human_reviewed"], 0)

    def test_duplicate_hidden_cases_rejected(self):
        d = copy.deepcopy(self.data)
        c = copy.deepcopy(d["cases"][0]); c["id"] = "duplicate"
        d["cases"].append(c)
        self.assertTrue(any("duplicate substantive" in e for e in validate(d, self.schema)["errors"]))

    def test_invalid_enum_and_future_date_rejected(self):
        d = copy.deepcopy(self.data)
        d["cases"][0]["hidden"]["contract_signed"] = "invalid"
        d["cases"][0]["hidden"]["start_date"] = "2099-01-01"
        errors = validate(d, self.schema)["errors"]
        self.assertTrue(any("invalid enum" in e for e in errors))
        self.assertTrue(any("future factual date" in e for e in errors))


class TestRuntimeControls(unittest.TestCase):
    def test_api_missing_key_fails_instead_of_mock(self):
        with self.assertRaisesRegex(ValueError, "refusing"):
            build_llm(LLMConfig(mode="api", api_key=""), strict=True)
        self.assertIsInstance(build_llm(LLMConfig(mode="mock", api_key="not-used"), strict=True), NullLLM)

    def test_model_failures_and_usage_counted(self):
        class Fake(BaseLLM):
            def complete(self, *args, **kwargs):
                return LLMResult("", False, "fake", prompt_tokens=3, error="timeout", attempts=3)
        a = AuditedLLM(Fake())
        a.complete([])
        self.assertEqual(a.summary()["failed_calls"], 1)
        self.assertEqual(a.summary()["http_attempts"], 3)
        self.assertEqual(a.summary()["prompt_tokens"], 3)

    def test_fixed_today_reaches_extractor(self):
        e = Extractor(ElementSchema(), NullLLM(), today=date(2026, 11, 27))
        r = e.extract("我是去年3月15日入职的。", {}, ["labor_dismissal"])
        self.assertEqual(r["facts"]["start_date"], "2025-03-15")

    def test_runtime_verifier_is_really_disabled(self):
        store = MemoryStore(":memory:")
        try:
            a = ConsultationAgent(StatuteCorpus(), ElementSchema(), store, llm=NullLLM(),
                                  use_verify=False, today="2026-11-27")
            with patch.object(a.verifier, "verify", side_effect=AssertionError("must not run")):
                r = a.handle("s", "公司把我辞退了", force_memo=True)
            self.assertTrue(r.verification["skipped"])
            self.assertNotIn("## 附：自动核验", r.memo)
        finally:
            store.close()


class TestNewlyExposedRuleBugs(unittest.TestCase):
    def test_partial_month_is_not_discarded(self):
        self.assertEqual(work_years("2021-03-01", "2026-03-15")["n"], 5.5)
        self.assertEqual(compute_compensation({"start_date": "2026-03-01", "dismiss_date": "2026-03-15",
                                              "monthly_wage": 10000}, pay_type="2N")["amount"], 10000)

    def test_negative_branches_return_real_analyses(self):
        cases = [("labor_overtime", {"overtime_exists": "没有"}, "F_OT_NONE"),
                 ("labor_double_pay", {"contract_signed": "已签书面合同"}, "F_DP_NONE"),
                 ("labor_noncompete", {"noncompete_signed": "没有签"}, "F_NC_NONE"),
                 ("labor_work_injury", {"injury_at_work": "不属于工伤"}, "F_WI_NONE")]
        for claim, facts, expected in cases:
            with self.subTest(claim=claim):
                a = analyse_many([claim], facts, "2026-11-27")
                self.assertIn(expected, [f.id for f in a.findings])
                self.assertFalse(any("分析出错" in g for g in a.gaps))

    def test_explicit_noncompete_amount_does_not_require_wage(self):
        a = analyse_many(["labor_noncompete"], {"noncompete_signed": "签了竞业限制协议",
                         "noncompete_months": 12, "noncompete_compensation": 4000}, "2026-11-27")
        self.assertEqual(a.metadata["per_claim"]["labor_noncompete"]["calculation"]["amount"], 48000)

    def test_odd_question_budget_is_not_exceeded(self):
        store = MemoryStore(":memory:")
        try:
            a = ConsultationAgent(StatuteCorpus(), ElementSchema(), store, llm=NullLLM(),
                                  budget=Budget(max_questions=3), use_voi=False, today="2026-11-27")
            r = a.handle("s", "公司把我辞退了")
            total = len(r.questions)
            for _ in range(3):
                r = a.handle("s", "我确实不知道。")
                total += len(r.questions)
            self.assertLessEqual(total, 3)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()

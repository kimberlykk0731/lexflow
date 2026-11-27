"""Regression cases taken from real API failures; no network in tests."""
import json
import unittest
from unittest.mock import patch

from lexflow.config import LLMConfig
from lexflow.elements import ElementSchema
from lexflow.extract import Extractor
from lexflow.issues import IssueTree
from lexflow.llm import BaseLLM, LLMResult, OpenAICompatLLM
from lexflow.memory import CaseState
from lexflow.memory import MemoryStore
from lexflow.agent import ConsultationAgent
from lexflow.corpus import StatuteCorpus
from lexflow.router import MatterRouter


class FixedModel(BaseLLM):
    @property
    def enabled(self):
        return True

    def __init__(self, result):
        self.result = result

    def complete(self, *args, **kwargs):
        return LLMResult(json.dumps(self.result, ensure_ascii=False), True, "test")


class TestRealFailureRegressions(unittest.TestCase):
    def setUp(self):
        self.schema = ElementSchema()
        self.router = MatterRouter(self.schema)

    def test_pregnancy_wage_protection_does_not_need_disambiguation(self):
        route = self.router.route("我在孕期，公司降低了工资待遇，想了解生育保护。")
        self.assertEqual(route.action, "proceed")
        self.assertIn("labor_maternity", route.claims)

    def test_resignation_and_expiry_are_dismissal_claims(self):
        for text in ("我自己辞职，想问解除劳动合同后还有经济补偿吗？",
                     "劳动合同到期，公司不续签，经济补偿应该怎么算？"):
            with self.subTest(text=text):
                route = self.router.route(text)
                self.assertEqual(route.claims, ["labor_dismissal"])

    def test_disability_correction_does_not_switch_to_traffic(self):
        state = CaseState("s", matter="labor", claims=["labor_work_injury"])
        route = self.router.route("更正一下，我之前说错了。关于伤残等级，九级。", state)
        self.assertEqual((route.matter, route.claims), ("labor", ["labor_work_injury"]))
        switched = self.router.route("换个问题，我被车撞了，是交通事故", state)
        self.assertEqual((switched.matter, switched.action), ("tort", "switch"))

    def test_contract_answer_does_not_add_a_claim(self):
        state = CaseState("s", matter="labor", claims=["labor_dismissal"])
        route = self.router.route("书面劳动合同方面，已签书面合同。", state)
        self.assertEqual(route.claims, state.claims)
        other = self.router.route("另外，我还想咨询试用期工资太低的问题", state)
        self.assertIn("labor_contract", other.claims)

    def test_invalid_model_claims_do_not_default_to_dismissal(self):
        for claims in (["tort_injury"], "labor_dismissal", [None, {}]):
            with self.subTest(claims=claims):
                router = MatterRouter(self.schema, FixedModel({"matter": "labor", "claims": claims}))
                result = router._llm_route("我想问一件事情")
                self.assertEqual(result.action, "clarify")
                self.assertEqual(result.claims, [])

    def test_period_preserves_current_text_and_rejects_other_claim_fields(self):
        model = FixedModel({"case_type": "tort_injury", "facts": {
            "overtime_period": "2026-02", "injury": "一般伤害"},
            "corrections": {}, "unknown": ["responsibility"]})
        result = Extractor(self.schema, model).extract("加班期间是2026年2月。", {}, ["labor_overtime"])
        self.assertEqual(result["facts"], {"overtime_period": "2026年2月"})
        self.assertEqual(result["case_type"], "labor_overtime")
        self.assertEqual(result["unknown"], [])

    def test_correction_only_response_updates_facts(self):
        model = FixedModel({"facts": {}, "corrections": {"disability_level": "九级"}, "unknown": []})
        result = Extractor(self.schema, model).extract("更正伤残等级为九级。", {}, ["labor_work_injury"])
        self.assertEqual(result["facts"]["disability_level"], "九级")

    def test_critical_fields_are_reachable_even_when_missing_from_elements(self):
        tree = IssueTree(self.schema)
        keys = {q.key for q in tree.frontier(["labor_contract"], {})}
        self.assertTrue({"monthly_wage", "start_date"} <= keys)
        self.assertIn("dismiss_date", {q.key for q in tree.frontier(["labor_noncompete"], {})})
        self.assertIn("wage_evidence", {q.key for q in tree.frontier(["labor_wage"], {})})

    def test_procedure_does_not_stop_when_only_deadlines_remain(self):
        store = MemoryStore(":memory:")
        try:
            state = CaseState("p", matter="labor", claims=["labor_procedure"])
            for key, value in {"arbitration_filed": "已申请", "claim_type": "要求赔偿金",
                               "amount_in_dispute": 20000}.items():
                state.set_fact(key, value)
            store.save(state)
            model = FixedModel({"facts": {}, "corrections": {}, "unknown": []})
            agent = ConsultationAgent(StatuteCorpus(), self.schema, store, llm=model, today="2026-11-27")
            result = agent.handle("p", "这些是我能确认的信息。")
            self.assertEqual(result.status, "asked")
            self.assertTrue({q["key"] for q in result.questions} &
                            {"arbitration_date", "arbitration_result", "court_filed", "deadline_aware"})
        finally:
            store.close()


class TestModelResponseContract(unittest.TestCase):
    def test_thinking_is_optional_and_empty_response_is_a_failure(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps({"choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                                   "usage": {"completion_tokens": 160}}).encode()

        with patch("urllib.request.urlopen", return_value=Response()) as request:
            model = OpenAICompatLLM(LLMConfig(mode="api", api_key="test", thinking="disabled"))
            result = model.complete([{"role": "user", "content": "test"}], max_tokens=160)
            self.assertEqual(json.loads(request.call_args.args[0].data)["thinking"], {"type": "disabled"})
            self.assertFalse(result.ok)
            self.assertEqual((result.finish_reason, result.completion_tokens), ("length", 160))
            self.assertIn("empty", result.error)
            model.cfg.thinking = ""
            model.complete([{"role": "user", "content": "test"}])
            self.assertNotIn("thinking", json.loads(request.call_args.args[0].data))

"""Routing must never silently default to a labour dismissal questionnaire."""
import unittest

from lexflow.config import LLMConfig
from lexflow.elements import ElementSchema
from lexflow.llm import build_llm
from lexflow.memory import CaseState
from lexflow.router import MatterRouter


class TestRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = ElementSchema()
        cls.router = MatterRouter(cls.schema, build_llm(LLMConfig(mode="mock")))

    def route(self, text, state=None):
        return self.router.route(text, state)

    def test_traffic_accident_alias_is_tort(self):
        r = self.route("交通肇事一般怎么处理")
        self.assertEqual(r.matter, "tort")
        self.assertIn("tort_injury", r.claims)
        self.assertNotIn("labor_dismissal", r.claims)

    def test_car_hit_person_is_tort(self):
        r = self.route("我开车把人撞了，对方十级伤残，想问怎么赔")
        self.assertEqual(r.matter, "tort")
        self.assertIn("tort_injury", r.claims)

    def test_commuting_accident_is_work_injury(self):
        r = self.route("下班路上出车祸算工伤吗")
        self.assertEqual(r.matter, "labor")
        self.assertIn("labor_work_injury", r.claims)

    def test_marriage_is_out_of_scope(self):
        r = self.route("我要离婚，孩子归谁")
        self.assertEqual(r.action, "out_of_scope")

    def test_weak_signal_asks_instead_of_defaulting(self):
        r = self.route("我被公司欺负了")
        self.assertEqual(r.action, "clarify")
        self.assertEqual(r.claims, [])

    def test_multi_claim_labour(self):
        r = self.route("公司欠我两个月工资，还让我天天加班")
        self.assertEqual(r.matter, "labor")
        self.assertIn("labor_wage", r.claims)
        self.assertIn("labor_overtime", r.claims)

    def test_short_answer_keeps_context(self):
        state = CaseState(session="s", matter="labor", claims=["labor_dismissal"])
        r = self.router.route("2026年3月15日通知的", state)
        self.assertEqual(r.action, "proceed")
        self.assertEqual(r.claims, ["labor_dismissal"])
        self.assertEqual(r.source, "context")

    def test_switch_to_tort(self):
        state = CaseState(session="s", matter="labor", claims=["labor_dismissal"])
        r = self.router.route("不是劳动，是交通事故，我被车撞了", state)
        self.assertEqual(r.matter, "tort")
        self.assertEqual(r.action, "switch")

    def test_mixed_loan_note(self):
        r = self.route("我被辞退了，另外我还想起诉一个借款纠纷")
        self.assertEqual(r.matter, "labor")
        self.assertIn("labor_dismissal", r.claims)
        self.assertIn("借贷", r.note)


if __name__ == "__main__":
    unittest.main()

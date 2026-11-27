"""End-to-end consultation on the two matters, including documents."""
import os
import tempfile
import unittest

from lexflow.agent import ConsultationAgent
from lexflow.config import LLMConfig
from lexflow.corpus import StatuteCorpus
from lexflow.documents import render_arbitration_application, render_legal_opinion
from lexflow.elements import ElementSchema
from lexflow.llm import build_llm
from lexflow.memory import MemoryStore


class TestAgentFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = StatuteCorpus()
        cls.schema = ElementSchema()
        cls.llm = build_llm(LLMConfig(mode="mock"))

    def agent(self, tmp):
        return ConsultationAgent(
            self.corpus, self.schema,
            MemoryStore(os.path.join(tmp, "m.sqlite")), llm=self.llm,
            today="2026-11-27")

    def test_dismissal_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.agent(tmp)
            r = a.handle("s", "公司把我辞退了，说我严重违纪，我想问能赔多少钱")
            self.assertEqual(r.status, "asked")
            self.assertEqual(r.claims, ["labor_dismissal"])
            self.assertTrue(any("严重违纪" in q["question"] or "制度" in q["question"]
                                for q in r.questions))
            for text in ("2026年3月15日通知的，员工手册从来没给我看过",
                         "我2021年5月入职的，月薪一万五",
                         "公司只有口头说我违纪，没有书面证据，解除前也没通知工会",
                         "制度制定没经过民主程序，我想要赔偿金",
                         "合同签了但没给我，公司叫北京测试科技有限公司"):
                r = a.handle("s", text)
            if r.status != "answered":
                r = a.handle("s", "请根据目前信息生成备忘录", force_memo=True)
            self.assertEqual(r.status, "answered")
            self.assertIn("要件链", r.memo)
            self.assertIn("违法解除", r.analysis["headline"])
            state = a.store.load("s")
            analysis = a._analysis_from_dict(state.last_analysis)
            letter = render_legal_opinion(analysis, state, self.schema)
            self.assertIn("法律意见书", letter)
            arb = render_arbitration_application(analysis, state, self.schema)
            self.assertIn("仲裁请求", arb)

    def test_traffic_flow_not_labour(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.agent(tmp)
            r = a.handle("t", "交通肇事一般怎么处理")
            self.assertEqual(r.claims, ["tort_injury"])
            self.assertNotIn("劳动", r.reply)

    def test_out_of_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.agent(tmp)
            r = a.handle("o", "我要离婚，孩子归谁")
            self.assertEqual(r.status, "out_of_scope")
            self.assertIn("婚姻家事", r.reply)

    def test_wage_and_overtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.agent(tmp)
            r = a.handle("w", "公司欠我两个月工资，还让我天天加班")
            self.assertIn("labor_wage", r.claims)
            self.assertIn("labor_overtime", r.claims)
            self.assertEqual(r.status, "asked")


if __name__ == "__main__":
    unittest.main()

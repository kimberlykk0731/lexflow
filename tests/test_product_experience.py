"""Question refinement, safe retry and editable document export regressions."""
import io
import json
import unittest
from contextlib import closing
from unittest.mock import patch

from lexflow.agent import ConsultationAgent
from lexflow.config import LLMConfig
from lexflow.corpus import StatuteCorpus
from lexflow.elements import ElementSchema
from lexflow.exports import export_docx, export_pdf, missing_fields, plain_text
from lexflow.issues import IssueTree
from lexflow.llm import NullLLM, OpenAICompatLLM
from lexflow.memory import MemoryStore
from lexflow.questions import QuestionComposer


class TestQuestionExperience(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.addCleanup(self.store.close)
        self.agent = ConsultationAgent(StatuteCorpus(), ElementSchema(), self.store,
                                       llm=NullLLM(), today="2026-11-27", use_voi=False)

    def test_known_month_gets_a_specific_refinement_not_the_same_question(self):
        tree = IssueTree(self.agent.schema)
        facts = {"start_date": "2021-05-01"}
        questions = tree.frontier(["labor_dismissal"], facts, precisions={"start_date": "month"})
        q = next(q for q in questions if q.key == "start_date")
        text = QuestionComposer().compose(q, facts, {})
        self.assertIn("2021-05", text)
        self.assertIn("具体几号", text)
        self.assertIn("跳过", text)

    def test_skip_one_question_does_not_skip_the_other(self):
        first = self.agent.handle("s", "公司把我辞退了，理由是严重违纪")
        keys = [q["key"] for q in first.questions]
        self.agent.handle("s", "暂时跳过这一项", skip_keys=[keys[0]])
        state = self.store.load("s")
        self.assertIn(keys[0], state.deferred)
        self.assertNotIn(keys[1], state.deferred)
        self.assertNotIn(keys[0], [q["key"] for q in self.store.last_result("s")["questions"]])

    def test_saying_unknown_does_not_loop_on_the_same_fields(self):
        first = self.agent.handle("s", "公司拖欠了我工资")
        keys = {q["key"] for q in first.questions}
        result = self.agent.handle("s", "我不知道")
        self.assertTrue(keys <= set(self.store.load("s").deferred))
        self.assertFalse(keys & {q["key"] for q in result.questions})
        self.assertNotEqual(result.coverage.get("rate"), 1)

    def test_later_fact_reactivates_a_deferred_field(self):
        first = self.agent.handle("s", "公司辞退了我")
        self.agent.handle("s", "跳过", skip_keys=[q["key"] for q in first.questions])
        result = self.agent.handle("s", "解除日期是2026年3月15日")
        self.assertEqual(self.store.load("s").value("dismiss_date"), "2026-03-15")
        self.assertNotIn("dismiss_date", self.store.load("s").deferred)


class TestRetryAndTelemetry(unittest.TestCase):
    def test_retry_rewinds_only_its_latest_turn_and_preserves_other_sessions(self):
        with closing(MemoryStore()) as store:
            agent = ConsultationAgent(StatuteCorpus(), ElementSchema(), store, llm=NullLLM())
            agent.handle("other", "交通事故怎么办")
            other_history = store.history("other")
            first = agent.handle("s", "公司辞退了我，月薪15000元")
            before = store.load("s").to_dict()
            store.prepare_request("s", "更正：月薪是12000元，不是15000元")
            agent.handle("s", "更正：月薪是12000元，不是15000元")
            retry = store.rewind_request("s")
            self.assertEqual(store.load("s").to_dict(), before)
            agent.handle("s", **retry)
            self.assertEqual(len(store.history("s")), 4)
            self.assertEqual(store.last_result("s")["turn"], first.turn + 1)
            self.assertEqual(store.load("s").value("monthly_wage"), 12000)
            self.assertEqual(store.history("other"), other_history)

    def test_cannot_rewind_a_request_after_another_message(self):
        with closing(MemoryStore()) as store:
            store.prepare_request("s", "test")
            store.log_turn("s", 1, "user", "test")
            store.log_turn("s", 2, "user", "new")
            with self.assertRaises(ValueError):
                store.rewind_request("s")

    def test_progress_reports_stages(self):
        with closing(MemoryStore()) as store:
            agent = ConsultationAgent(StatuteCorpus(), ElementSchema(), store, llm=NullLLM())
            steps = []
            agent.handle("s", "公司拖欠我工资", on_progress=steps.append)
            self.assertIn("正在整理您提供的事实…", steps)
            self.assertIn("正在组织下一步要问的问题…", steps)

    def test_empty_response_reports_usage_without_request_contents(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self):
                return json.dumps({"choices": [{"message": {"content": ""}}],
                                   "usage": {"prompt_tokens": 11, "completion_tokens": 2}}).encode()
        model = OpenAICompatLLM(LLMConfig(mode="api", api_key="secret-test"))
        with patch("urllib.request.urlopen", return_value=Response()):
            model.complete([{"role": "user", "content": "private-input"}])
        self.assertFalse(model.events[0]["ok"])
        self.assertEqual(model.events[0]["prompt_tokens"], 11)
        self.assertIn("空内容", model.events[0]["error"])
        self.assertNotIn("secret-test", json.dumps(model.events))
        self.assertNotIn("private-input", json.dumps(model.events))


class TestDocumentExports(unittest.TestCase):
    SAMPLE = "# 仲裁申请书草稿\n\n申请人：________\n\n## 仲裁请求\n\n1. 支付工资 20,000 元。\n\n| 材料 | 状态 |\n|---|---|\n| 劳动合同 | 待核对 |\n"

    def test_word_keeps_edited_chinese_content_and_table(self):
        try:
            from docx import Document
        except ImportError:
            self.skipTest("optional python-docx not installed")
        edited = self.SAMPLE.replace("________", "测试申请人")
        doc = Document(io.BytesIO(export_docx(edited)))
        self.assertIn("申请人：测试申请人", "\n".join(p.text for p in doc.paragraphs))
        self.assertEqual(doc.tables[0].cell(1, 0).text, "劳动合同")

    def test_pdf_is_generated_and_blank_fields_stay_visible(self):
        try:
            import reportlab
        except ImportError:
            self.skipTest("optional reportlab not installed")
        self.assertTrue(export_pdf(self.SAMPLE).startswith(b"%PDF-"))
        self.assertEqual(missing_fields(self.SAMPLE), ["申请人：________"])
        self.assertEqual(missing_fields(self.SAMPLE.replace("________", "测试申请人")), [])

    def test_drafts_are_scoped_by_session_and_kind(self):
        with closing(MemoryStore()) as store:
            store.save_draft("a", "申请书", "编辑内容", "v1")
            self.assertEqual(store.draft("a", "申请书")["content"], "编辑内容")
            self.assertIsNone(store.draft("b", "申请书"))
            self.assertIsNone(store.draft("a", "意见书"))

    def test_copy_preserves_amounts_and_link_destinations(self):
        text = plain_text("**金额**：12000元 [来源](https://example.com)")
        self.assertEqual(text, "金额：12000元 来源（https://example.com）")


if __name__ == "__main__":
    unittest.main()

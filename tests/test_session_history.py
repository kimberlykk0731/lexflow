"""Restart recovery, bounded model context and reference-only follow-ups."""
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from lexflow.agent import ConsultationAgent
from lexflow.corpus import StatuteCorpus
from lexflow.elements import ElementSchema
from lexflow.extract import Extractor
from lexflow.llm import BaseLLM, LLMResult, NullLLM
from lexflow.memory import CaseState, MemoryStore


class RecordingLLM(BaseLLM):
    name = "recording-test"

    def __init__(self):
        self.prompts = []

    @property
    def enabled(self):
        return True

    def complete(self, messages, **kwargs):
        self.prompts.append(messages)
        text = ('{"facts":{},"corrections":{},"unknown":[]}'
                if "信息抽取模块" in messages[0]["content"]
                else "第二点问的是员工手册是否向您公示或告知。")
        return LLMResult(text=text, ok=True, model=self.name,
                         prompt_tokens=10, completion_tokens=10)


class TestSessionHistory(unittest.TestCase):
    def test_restart_restores_artifacts_corrections_and_turn_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.sqlite"
            with closing(MemoryStore(path)) as store:
                agent = ConsultationAgent(StatuteCorpus(), ElementSchema(), store,
                                          llm=NullLLM(), today="2026-11-27")
                first = agent.handle("one", "公司把我辞退了，月薪一万五")
                agent.handle("one", "更正：月薪是12000元，不是15000元")
                before = store.load("one")
                snapshot = store.last_result("one")
                history = store.history("one")
            with closing(MemoryStore(path)) as store:
                self.assertEqual(store.history("one"), history)
                self.assertEqual(store.last_result("one"), snapshot)
                self.assertEqual(store.load("one").to_dict(), before.to_dict())
                self.assertEqual(store.session_date("one"), "2026-11-27")
                self.assertTrue(store.load("one").superseded())
                resumed = ConsultationAgent(StatuteCorpus(), ElementSchema(), store,
                                            llm=NullLLM(), today=store.session_date("one"))
                result = resumed.handle("one", "解除日期是2026年3月15日")
                self.assertEqual(result.turn, first.turn + 2)
                self.assertEqual(store.load("one").value("monthly_wage"), 12000)
                self.assertEqual(len(store.history("one")), 6)

    def test_legacy_sessions_are_listed_and_never_cross_contaminate(self):
        with closing(MemoryStore()) as store:
            for sid, title in [("a", "公司欠我工资"), ("b", "交通事故")]:
                store.save(CaseState(session=sid))
                store.log_turn(sid, 1, "user", title)
            self.assertEqual({r["title"] for r in store.list_sessions()},
                             {"公司欠我工资", "交通事故"})
            self.assertEqual(store.recent_history("a"),
                             [{"role": "user", "content": "公司欠我工资"}])
            self.assertIsNone(store.last_result("missing"))
            self.assertFalse(store.session_exists("missing"))

    def test_recent_context_is_bounded_but_full_history_is_preserved(self):
        with closing(MemoryStore()) as store:
            for turn in range(20):
                store.log_turn("a", turn, "user", f"{turn}:" + "x" * 2000)
            recent = store.recent_history("a", limit=6, max_chars=4500)
            self.assertLessEqual(len(recent), 6)
            self.assertLessEqual(sum(len(m["content"]) for m in recent), 4500)
            self.assertTrue(recent[-1]["content"].startswith("19:"))
            self.assertEqual(len(store.history("a")), 20)

    def test_extractor_receives_recent_conversation(self):
        llm = RecordingLLM()
        history = [{"role": "assistant", "content": "您有没有签收员工手册？"}]
        Extractor(ElementSchema(), llm).extract(
            "有的", {}, ["labor_dismissal"], history=history)
        payload = json.loads(llm.prompts[0][1]["content"])
        self.assertEqual(payload["recent_history"], history)
        self.assertEqual(payload["user_text"], "有的")

    def test_explanation_preserves_facts_and_current_artifacts(self):
        llm = RecordingLLM()
        with closing(MemoryStore()) as store:
            state = CaseState(session="a", claims=["labor_dismissal"], matter="labor")
            state.set_fact("monthly_wage", 15000)
            state.set_fact("monthly_wage", 12000)
            store.save(state)
            store.log_turn("a", 1, "user", "公司辞退我了")
            store.log_turn("a", 1, "assistant", "1. 解除日期？\n2. 员工手册公示了吗？")
            store.log_trace("a", 1, {"memo": "当前备忘录", "analysis": {},
                                    "claims": ["labor_dismissal"], "questions": [{"key": "x"}]})
            agent = ConsultationAgent(StatuteCorpus(), ElementSchema(), store, llm=llm)
            result = agent.handle("a", "你刚才说的第二点是什么意思？")
            self.assertEqual(result.status, "explained")
            self.assertIn("员工手册", result.reply)
            self.assertEqual(result.memo, "当前备忘录")
            self.assertEqual(result.revision, state.revision)
            self.assertEqual(store.load("a").value("monthly_wage"), 12000)
            self.assertEqual(len(llm.prompts), 1)
            payload = json.loads(llm.prompts[0][1]["content"])
            self.assertEqual(payload["current_facts"]["monthly_wage"], 12000)
            self.assertIn("2. 员工手册", payload["recent_history"][-1]["content"])

    def test_corrections_are_not_misrouted_to_explanation(self):
        self.assertFalse(ConsultationAgent._history_question(
            "更正：刚才说错了，月薪不是15000，是12000，为什么没改？"))
        self.assertTrue(ConsultationAgent._history_question("上面第二点能再解释一下吗"))
        self.assertTrue(ConsultationAgent._history_question("你还记得我之前说的月薪是多少吗？"))


if __name__ == "__main__":
    unittest.main()

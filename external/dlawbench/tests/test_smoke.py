"""Smoke tests for the DLawBench adapter (stdlib unittest, offline)."""
from __future__ import annotations

import json
import sys
import unittest
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "upstream" / "src"))

from bootstrap import cluster_bootstrap  # noqa: E402
from client_sim import ClientSimulator  # noqa: E402
from judge import judge_reply  # noqa: E402
from policy import LawyerPolicy, model_name, policy_from_model  # noqa: E402
from server import ShimServer  # noqa: E402
from verify import library_leakage  # noqa: E402


SYSTEM = """你是一名拥有丰富诉讼经验的执业律师。一位客户来找你进行法律咨询。

客户的开场白是：
"律师你好，我是张某，我因为交通事故被追究刑事责任。"

【你的工具】
1. talk_to_client(message) — 向客户提问或回应。
2. write_memo(content) — 提交法律备忘录。
"""


def lawyer_messages(history: list[dict]) -> list[dict]:
    return [{"role": "system", "content": SYSTEM}, *history,
            {"role": "user", "content": "[系统] 当前第 0/10 轮，剩余 10 轮。"}]


class PolicyTests(unittest.TestCase):
    def test_answer_first_writes_memo_without_questions(self):
        reply = json.loads(LawyerPolicy("answer_first").respond(lawyer_messages([])))
        self.assertEqual(reply["tool"], "write_memo")
        for section in ("案情概要", "关键事实", "法律问题", "风险评估", "下一步建议"):
            self.assertIn(section, reply["content"])

    def test_gate_only_asks_first(self):
        reply = json.loads(LawyerPolicy("gate_only").respond(lawyer_messages([])))
        self.assertEqual(reply["tool"], "talk_to_client")
        self.assertTrue(reply["message"])

    def test_gate_only_writes_memo_when_out_of_turns(self):
        history = [
            {"role": "assistant", "content": json.dumps(
                {"tool": "talk_to_client", "message": "请说一下经过。"}, ensure_ascii=False)},
            {"role": "user", "content": json.dumps(
                {"client_response": "2024年6月20日我开车撞了人。", "turn": 1,
                 "remaining_turns": 0}, ensure_ascii=False)},
        ]
        messages = lawyer_messages(history)
        messages[-1]["content"] = "[系统] 当前第 10/10 轮，剩余 0 轮。"
        reply = json.loads(LawyerPolicy("full").respond(messages))
        self.assertEqual(reply["tool"], "write_memo")

    def test_checklist_9_model_name(self):
        self.assertEqual(model_name("checklist_9"), "lexflow-checklist-9")
        self.assertEqual(policy_from_model("lexflow-checklist-9"), "checklist_9")


class ClientTests(unittest.TestCase):
    def test_reveals_matching_fact_only(self):
        system = """【你知道的事实】
- 2024年6月20日晚上7点，我开着货车在路口撞了人。
- 公司还欠我两个月工资一共一万二。

【对话规则】
"""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "事故是什么时间、怎么发生的？"},
        ]
        answer = ClientSimulator("P_WD").respond(messages)
        self.assertIn("货车", answer)
        self.assertNotIn("工资", answer)

    def test_fallback_is_persona_specific(self):
        system = "【你知道的事实】\n- 我借给朋友五万元。\n\n【对话规则】\n"
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": "请说说案发经过。"}]
        answer = ClientSimulator("P_CS").respond(messages)
        self.assertTrue(answer)


class JudgeTests(unittest.TestCase):
    def test_memo_judge_shape(self):
        prompt = (
            "【评估标准 — 备忘录要点】（每项 0 或 1 分）\n"
            "1. 分析自首情节\n2. 分析赔偿谅解\n\n"
            "【评估标准 — 律师问诊动作】（每项 0 或 1 分，根据对话记录判断律师是否执行了该动作）\n"
            "1. 追问到案经过\n2. 追问赔偿情况\n\n"
            "【对话记录】\n律师（第1轮）：您到案经过是怎样的？\n客户：我主动报警。\n\n"
            "【备忘录内容】\n## 法律问题\n本案应分析自首情节。\n\n"
            "请输出 JSON"
        )
        reply = json.loads(judge_reply([{"role": "user", "content": prompt}]))
        self.assertEqual(len(reply["memo_expectation_scores"]), 2)
        self.assertEqual(len(reply["expected_action_scores"]), 2)
        self.assertIn(reply["memo_expectation_scores"][0], (0, 1))

    def test_dag_judge_shape(self):
        prompt = (
            "集合 A：案件事实（共 1 条，含客户认知和实际情况）\n"
            "━━\n事实F1（undisputed）:\n  客户认知: 2024年事故\n  实际情况: 2024年事故\n\n"
            "━━\n对话记录（律师与客户的完整问诊过程）\n━━\n客户：2024年事故\n\n"
            "━━\n集合 B：律师备忘录\n━━\n## 关键事实\n- 2024年事故\n\n请输出 JSON"
        )
        reply = json.loads(judge_reply([{"role": "user", "content": prompt}]))
        self.assertEqual(reply["discovery"]["covered"], ["F1"])
        self.assertEqual(reply["accuracy"]["correct"], ["F1"])


class BootstrapTests(unittest.TestCase):
    def test_interval_brackets_mean(self):
        rows = {
            "p": [{"case_id": f"c{i}", "x": i / 10} for i in range(10)],
        }
        out = cluster_bootstrap(rows, ["x"], n_boot=300, seed=1)
        mean, lo, hi = out["p"]["x"]
        self.assertLessEqual(lo, mean)
        self.assertLessEqual(mean, hi)


class LibraryTests(unittest.TestCase):
    def test_issue_library_has_no_case_fingerprints(self):
        """The hand-written issue library must not carry case-specific content."""
        self.assertEqual(library_leakage(), [])


class ServerTests(unittest.TestCase):
    def test_http_roundtrip(self):
        server = ShimServer(port=0).start()
        try:
            payload = json.dumps({
                "model": "lexflow-answer-first",
                "messages": lawyer_messages([]),
            }).encode()
            request = urllib.request.Request(
                server.base_url + "/chat/completions", data=payload,
                headers={"Content-Type": "application/json"},
            )
            body = json.load(urllib.request.urlopen(request, timeout=30))
            content = body["choices"][0]["message"]["content"]
            self.assertEqual(json.loads(content)["tool"], "write_memo")
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()

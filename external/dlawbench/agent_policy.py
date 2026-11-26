"""Real LexFlow agent shim for the DLawBench lawyer protocol.

This is the adapter the hand-off describes: DLawBench talks to an
OpenAI-compatible endpoint, and each turn is forwarded to
``ConsultationAgent.handle``.  It is intentionally separate from
``policy.py`` (the fixed-checklist simulation) so the report can distinguish a
real-agent case study from the protocol simulation.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

try:  # package import
    from .policy import MAX_TURNS_RE, OPENING_RE, TURN_RE
except ImportError:  # script import
    from policy import MAX_TURNS_RE, OPENING_RE, TURN_RE

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

AGENT_POLICIES = ("answer_first", "gate_only", "full")


def agent_model(policy: str) -> str:
    return "lexflow-agent-" + policy.replace("_", "-")


def policy_from_agent_model(name: str) -> str | None:
    lower = (name or "").strip().lower()
    for policy in AGENT_POLICIES:
        if lower == agent_model(policy):
            return policy
    return None


class AgentPolicy:
    """One real ``ConsultationAgent`` per policy, with per-session state."""

    def __init__(self, policy: str):
        if policy not in AGENT_POLICIES:
            raise ValueError(f"unknown agent policy: {policy}")
        from lexflow.agent import ConsultationAgent
        from lexflow.config import LLMConfig
        from lexflow.corpus import StatuteCorpus
        from lexflow.elements import ElementSchema
        from lexflow.llm import build_llm
        from lexflow.memory import MemoryStore

        switches = {
            "answer_first": dict(use_gate=False, use_verify=False, use_repair=False),
            "gate_only": dict(use_gate=True, use_verify=False, use_repair=False),
            "full": dict(use_gate=True, use_verify=True, use_repair=True),
        }[policy]
        today = os.getenv("LEXFLOW_AGENT_TODAY", "2024-12-31")
        self.agent = ConsultationAgent(
            StatuteCorpus(),
            ElementSchema(),
            MemoryStore(":memory:"),
            build_llm(LLMConfig()),
            today=today,
            use_memory=True,
            use_cache=True,
            use_revision=True,
            **switches,
        )
        self.started: set[str] = set()
        self.cache: dict[tuple[str, int, str], str] = {}

    def respond(self, messages: list[dict]) -> str:
        state = self._parse(messages)
        session = hashlib.sha1(state["system"].encode("utf-8")).hexdigest()
        remaining = max(0, state["max_turns"] - state["turn"])
        force_memo = remaining <= 1

        if session in self.started:
            text = state["last_client"]
            if not text:
                return json.dumps(
                    {"tool": "talk_to_client", "message": "请继续说明。"},
                    ensure_ascii=False,
                )
        else:
            text = state["opening"]
            self.started.add(session)

        key = (session, state["turn"], text)
        if key in self.cache:
            return self.cache[key]

        result = self.agent.handle(session, text, force_memo=force_memo)
        if result.status == "answered" and result.memo:
            payload = {"tool": "write_memo", "content": _format_for_dlawbench(result.memo)}
        else:
            payload = {"tool": "talk_to_client", "message": result.reply or "请继续说明。"}
        content = json.dumps(payload, ensure_ascii=False)
        self.cache[key] = content
        return content

    def _parse(self, messages: list[dict]) -> dict:
        system = ""
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content") or ""
                break
        opening_match = OPENING_RE.search(system)
        opening = opening_match.group(1).strip() if opening_match else ""
        max_match = MAX_TURNS_RE.search(system)
        max_turns = int(max_match.group(1)) if max_match else 10

        turn = 0
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            found = TURN_RE.search(msg.get("content") or "")
            if found:
                turn = int(found.group(1))
                max_turns = int(found.group(2))
                break

        last_client = ""
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            try:
                payload = json.loads(msg.get("content") or "")
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("client_response"):
                last_client = str(payload["client_response"])
                break
        return {
            "system": system,
            "opening": opening,
            "turn": turn,
            "max_turns": max_turns,
            "last_client": last_client,
        }


_AGENTS: dict[str, AgentPolicy] = {}


def _format_for_dlawbench(memo: str) -> str:
    """Map LexFlow's memo headings onto DLawBench's required sections.

    The content is LexFlow's own; this is a formatting adapter only.  The
    mapping is needed because DLawBench's format check looks for the five
    sections in its lawyer system prompt.
    """
    sections: dict[str, list[str]] = {}
    current = ""
    for line in memo.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current:
            sections[current].append(line)

    def pick(*keys: str) -> str:
        blocks = []
        for heading, body in sections.items():
            if any(key in heading for key in keys):
                block = "\n".join(body).strip()
                if block:
                    blocks.append(block)
        return "\n\n".join(blocks).strip()

    summary = pick("结论摘要")
    facts = pick("事实状态")
    issues = pick("争点分析")
    risks = pick("信息缺口", "自动核验")
    next_steps = pick("下一步")
    citations = pick("引用与版本")
    if not (summary or facts or issues or next_steps):
        return memo

    lines = ["# 法律咨询备忘录", ""]
    lines += ["## 案情概要", "", summary or "（详见关键事实与法律问题。）", ""]
    lines += ["## 关键事实", "", facts or "（无结构化事实表。）", ""]
    lines += ["## 法律问题", "", issues or "（暂无可分析的争点。）", ""]
    lines += ["## 风险评估", "", risks or "（无额外风险提示。）", ""]
    lines += ["## 下一步建议", "", next_steps or "（无额外建议。）", ""]
    if citations:
        lines += ["## 引用与版本", "", citations, ""]
    return "\n".join(lines).strip() + "\n"


def get_agent_policy(policy: str) -> AgentPolicy:
    if policy not in _AGENTS:
        _AGENTS[policy] = AgentPolicy(policy)
    return _AGENTS[policy]

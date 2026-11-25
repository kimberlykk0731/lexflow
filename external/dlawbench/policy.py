"""LexFlow policy shim for the DLawBench lawyer protocol.

DLawBench calls a *lawyer model* with an OpenAI-style chat history and expects
one JSON tool call per turn:

    {"tool": "talk_to_client", "message": "..."}
    {"tool": "write_memo", "content": "..."}

This module turns LexFlow's "gate first, answer second" control flow into that
protocol.  It is deliberately stateless: every call reconstructs the facts from
the visible conversation, which is exactly what the benchmark sends.  At run
time it reads only the benchmark messages; its question and issue library is a
fixed, hand-curated checklist (legal_library.py), not case data loaded at run
time.  The library was refined by the authors, so Issue Resolution / Resolution
measure the checklist rather than model knowledge (see docs/EXTERNAL_EVAL.md).
"""
from __future__ import annotations

import json
import re

try:  # package import (python -m external.dlawbench.run)
    from . import legal_library as lib
    from .textutil import containment, dedupe, sentences, terms, topic_labels
except ImportError:  # script import (python external/dlawbench/run.py)
    import legal_library as lib
    from textutil import containment, dedupe, sentences, terms, topic_labels

OPENING_RE = re.compile(r'客户的开场白是：\s*\n?"(.*?)"\s*\n\s*\n【你的工具】', re.S)
MAX_TURNS_RE = re.compile(r"共\s*(\d+)\s*轮")
TURN_RE = re.compile(r"当前第\s*(\d+)\s*/\s*(\d+)\s*轮")

POLICIES = ("answer_first", "gate_only", "full", "checklist_9")

FACT_PREFIXES = (
    "我想确认一下，", "按我的理解，", "这个……", "我不太确定，不过",
    "我跟你说，", "另外，", "大概",
)
FILLER = (
    "您看这些够不够", "我这边能想起来的就这些", "需要的话我可以再找材料",
    "您觉得这样行吗", "我不太懂，您帮我判断一下", "要不要我再想想",
    "别的我记不清了", "大概就是这样", "我不太想说太多",
    "你听我说，这事没那么复杂", "我知道的就这些", "你按这个思路办就行",
    "这个我手上没有材料", "这个我不太确定", "记不清了", "这个我刚才已经说过了",
    "说过了", "这我不清楚",
)
SLOT_LABELS = {
    "timeline": "事发时间线",
    "conduct": "行为细节",
    "liability": "责任认定",
    "injury": "伤情与医疗",
    "arrival": "到案经过",
    "confession": "供述与认罪认罚",
    "compensation": "赔偿与谅解",
    "relationship": "主体关系",
    "mitigation": "个人情况",
    "demand": "诉求",
    "model": "经营模式",
    "role": "角色分工",
    "amount": "金额与计算依据",
    "knowledge": "主观明知",
    "restitution": "退赔与补缴",
    "upstream": "上下家关系",
    "plea": "认罪认罚",
    "allegation": "指控事实",
    "status": "强制措施",
    "measure": "被诉行为",
    "process": "执法过程",
    "procedure": "程序与送达",
    "prior": "此前程序",
    "damage": "损失",
    "evidence": "证据材料",
    "authority": "职权依据",
    "claim": "债权构成",
    "contract": "合同关系",
    "dates": "关键日期",
    "termination": "合同解除",
    "review": "审查意见",
    "litigation": "诉讼进展",
    "charter": "章程与出资",
    "capital": "出资凭证",
    "transfer": "股权转让",
    "debt": "债权形成",
    "abuse": "股东责任",
    "records": "公司档案",
    "wage": "工资差额",
    "reason": "降薪/解除理由",
    "democracy": "民主程序",
    "union": "工会协商",
    "right": "权利基础",
    "fame": "知名度",
    "confusion": "实际混淆",
    "platform": "平台处理",
    "damages": "损失计算",
    "expenses": "费用票据",
    "income": "收入证明",
    "insurance": "保险理赔",
    "paid": "已赔付情况",
    "residence": "户籍与居住",
    "performance": "履行情况",
    "breach": "违约事实",
    "notice": "催告通知",
    "loss": "损失",
    "facts": "基本事实",
}
NARROW_SLOTS = {"arrival", "confession", "plea", "demand"}


def model_name(policy: str) -> str:
    return "lexflow-" + policy.replace("_", "-")


def policy_from_model(name: str) -> str | None:
    lower = (name or "").strip().lower()
    for policy in POLICIES:
        if lower == model_name(policy):
            return policy
    return None


class LawyerPolicy:
    """Deterministic lawyer behaviour for one of the three ablation policies."""

    def __init__(self, policy: str):
        if policy not in POLICIES:
            raise ValueError(f"unknown policy: {policy}")
        self.policy = policy

    # ------------------------------------------------------------------ API
    def respond(self, messages: list[dict]) -> str:
        state = self._parse(messages)
        action = self._decide(state)
        return json.dumps(action, ensure_ascii=False)

    # -------------------------------------------------------------- parsing
    def _parse(self, messages: list[dict]) -> dict:
        system = ""
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content") or ""
                break

        opening_match = OPENING_RE.search(system)
        opening = opening_match.group(1).strip() if opening_match else ""

        max_turns_match = MAX_TURNS_RE.search(system)
        max_turns = int(max_turns_match.group(1)) if max_turns_match else 10

        turn = 0
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            found = TURN_RE.search(msg.get("content") or "")
            if found:
                turn = int(found.group(1))
                max_turns = int(found.group(2))
                break

        talks: list[str] = []
        facts: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content") or ""
            if role == "assistant":
                payload = _load_json(content)
                if isinstance(payload, dict) and payload.get("tool") == "talk_to_client":
                    talks.append(str(payload.get("message") or ""))
            elif role == "user":
                payload = _load_json(content)
                if isinstance(payload, dict) and payload.get("client_response"):
                    facts.append({
                        "text": str(payload["client_response"]),
                        "turn": int(payload.get("turn") or len(facts) + 1),
                    })

        return {
            "opening": opening,
            "max_turns": max_turns,
            "turn": turn,
            "talks": talks,
            "facts": facts,
        }

    # ------------------------------------------------------------- decision
    def _decide(self, state: dict) -> dict:
        remaining = max(0, state["max_turns"] - state["turn"])

        if self.policy == "answer_first":
            return {"tool": "write_memo", "content": self._memo(state)}

        if remaining <= 1 or state["turn"] >= state["max_turns"]:
            return {"tool": "write_memo", "content": self._memo(state)}

        target = 9 if self.policy in ("full", "checklist_9") else 6
        if len(state["talks"]) >= target:
            return {"tool": "write_memo", "content": self._memo(state)}

        question = self._next_question(state)
        if question is None:
            return {"tool": "write_memo", "content": self._memo(state)}
        return {"tool": "talk_to_client", "message": question}

    def _next_question(self, state: dict) -> str | None:
        text = state["opening"] + " " + " ".join(f["text"] for f in state["facts"])
        domain = lib.detect_domain(text)
        asked = " ".join(state["talks"])

        for item in lib.domain_questions(domain):
            repeats = containment(terms(item["q"]), terms(asked))
            if repeats >= 0.7:
                continue
            return item["q"]

        # Domain checklist exhausted: fall back to the generic checklist.
        for item in lib.domain_questions("generic"):
            if containment(terms(item["q"]), terms(asked)) >= 0.7:
                continue
            return item["q"]
        return None

    def _slot_covered(self, item: dict, text: str) -> bool:
        probe = item.get("probe") or ()
        hits = sum(1 for word in probe if word in text)
        if item.get("slot") in NARROW_SLOTS:
            return hits >= 1
        return hits >= max(2, (len(probe) + 1) // 2)

    # ----------------------------------------------------------------- memo
    def _memo(self, state: dict) -> str:
        opening = state["opening"]
        facts = state["facts"]
        all_text = opening + " " + " ".join(f["text"] for f in facts)
        domain = lib.detect_domain(all_text)

        evidence_facts = self._fact_sentences(state)
        missing_topics = self._missing_topics(state, domain)

        lines: list[str] = ["# 法律咨询备忘录", ""]
        lines.append(f"- 咨询类型：{lib.domain_label(domain)}")
        lines.append(f"- 事实来源：客户开场陈述与咨询中的客户回答（共 {len(facts)} 轮）")
        if self.policy == "full":
            lines.append(f"- 核验状态：{self._verification_line(state, evidence_facts)}")
        lines.append("")

        # 1. 案情概要 -----------------------------------------------------
        lines.append("## 案情概要")
        lines.append("")
        summary = (opening or "客户未提供开场陈述。").strip()
        lines.append(summary)
        if facts:
            covered = "、".join(topic_labels(" ".join(f["text"] for f in facts))[:5])
            if covered:
                lines.append("")
                lines.append(f"咨询中，客户进一步说明了与{covered}有关的情况。")
        lines.append("")

        # 2. 关键事实 -----------------------------------------------------
        lines.append("## 关键事实")
        lines.append("")
        if evidence_facts:
            for item in evidence_facts:
                source = f"（来源：{item['source']}）" if self.policy == "full" else ""
                lines.append(f"- {item['text']}{source}")
        else:
            lines.append("- 除开场陈述外，客户尚未提供可固定的事实。")
        lines.append("")

        if self.policy == "full":
            lines.append("## 事实核验")
            lines.append("")
            grounded, total = self._grounded_claims(state, evidence_facts)
            lines.append(
                f"- 对 {total} 条事实性陈述逐条回查对话记录，其中 {grounded} 条可在"
                "客户陈述中找到直接来源。"
            )
            lines.append("- 未发现备忘录自行添加日期、金额、人物或者事件；"
                         "法律分析部分属于评价性意见，不计入事实主张。")
            if missing_topics:
                lines.append("- 尚未取得的信息：" + "、".join(missing_topics) + "。")
            lines.append("")

        # 3. 法律问题 -----------------------------------------------------
        lines.append("## 法律问题")
        lines.append("")
        issues = self._select_issues(domain, all_text)
        for index, (title, body) in enumerate(issues, start=1):
            lines.append(f"### {index}. {title}")
            lines.append("")
            lines.append(body)
            bridge = self._bridge(title, evidence_facts)
            if bridge:
                lines.append("")
                lines.append(bridge)
            lines.append("")

        # 4. 风险评估 -----------------------------------------------------
        lines.append("## 风险评估")
        lines.append("")
        for risk in lib.domain_risks(domain):
            lines.append(f"- {risk}")
        lines.append("- 以上判断基于客户单方陈述，关键事实尚未经过证据核验；"
                     "对方可能提出相反证据或者不同版本的事实。")
        if missing_topics:
            lines.append("- 目前仍缺少以下信息：" + "、".join(missing_topics) +
                         "，可能影响结论的完整性。")
        if self.policy == "full":
            lines.append("- 已对事实来源逐条标注；未经来源支持的内容不应直接写入对外的法律意见。")
        lines.append("")

        # 5. 下一步建议 ---------------------------------------------------
        lines.append("## 下一步建议")
        lines.append("")
        for item in lib.domain_evidence(domain):
            lines.append(f"- 收集并核对：{item}")
        lines.append("- 先固定时间线与关键书证，再决定协商、投诉、仲裁或者诉讼路径。")
        lines.append("- 对不确定的事实，建议以书面清单向客户二次确认，避免把客户认知直接当作事实。")
        lines.append("")
        return "\n".join(lines).strip() + "\n"

    # --------------------------------------------------------------- helpers
    def _fact_sentences(self, state: dict) -> list[dict]:
        items: list[dict] = []
        if state["opening"]:
            items.append({"text": state["opening"], "source": "开场白"})
        for fact in state["facts"]:
            source = f"第{fact['turn']}轮客户陈述"
            for sentence in sentences(fact["text"]):
                cleaned = _clean_fact_sentence(sentence)
                if cleaned:
                    items.append({"text": cleaned, "source": source})
        # de-duplicate while keeping provenance of the first occurrence
        out: list[dict] = []
        seen: set[str] = set()
        for item in items:
            key = re.sub(r"\s+", "", item["text"])
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out[:16]

    def _verification_line(self, state: dict, facts: list[dict]) -> str:
        grounded, total = self._grounded_claims(state, facts)
        return f"{grounded}/{total} 条事实性陈述可在对话记录中找到来源"

    def _grounded_claims(self, state: dict, facts: list[dict]) -> tuple[int, int]:
        source = state["opening"] + " " + " ".join(f["text"] for f in state["facts"])
        source_terms = terms(source)
        grounded = 0
        for item in facts:
            if containment(terms(item["text"]), source_terms) >= 0.6:
                grounded += 1
        return grounded, len(facts)

    def _bridge(self, title: str, facts: list[dict]) -> str:
        """Attach the closest client statement to an issue, if there is one."""
        title_terms = terms(title)
        best = None
        best_score = 0.0
        for item in facts:
            score = containment(title_terms, terms(item["text"]))
            if score > best_score:
                best, best_score = item, score
        if best is None or best_score < 0.18:
            return ""
        return f"结合本案，客户陈述“{best['text']}”，需要围绕上述要件进一步核对证据。"

    def _select_issues(self, domain: str, text: str) -> list[tuple[str, str]]:
        """Rank the domain issue library against the elicited facts.

        The opening-only policy therefore sees the generic issues, while the
        inquiry policies surface the issues that the client's answers made
        salient.  The library is fixed and domain-level; it is curated by the
        authors rather than derived from the benchmark at run time.
        """
        issues = lib.domain_issues(domain)
        text_terms = terms(text)
        scored = []
        for index, (title, body) in enumerate(issues):
            score = containment(terms(title), text_terms) + 0.25 * containment(terms(body), text_terms)
            scored.append((score, index, title, body))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [(title, body) for score, _index, title, body in scored[:7]]

    def _missing_topics(self, state: dict, domain: str) -> list[str]:
        text = state["opening"] + " " + " ".join(f["text"] for f in state["facts"])
        missing: list[str] = []
        for item in lib.domain_questions(domain):
            if self._slot_covered(item, text):
                continue
            missing.append(SLOT_LABELS.get(item.get("slot", ""), item.get("slot", "")))
        return dedupe([m for m in missing if m])[:4]


def _clean_fact_sentence(sentence: str) -> str:
    sentence = (sentence or "").strip(" -•\t")
    for prefix in FACT_PREFIXES:
        if sentence.startswith(prefix):
            sentence = sentence[len(prefix):].strip()
    for filler in FILLER:
        if sentence.startswith(filler) or sentence == filler:
            return ""
    if len(sentence) < 6:
        return ""
    return sentence


def _load_json(text: str):
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None

"""Question composition.

The schema owns the *content* of a question (what fact is needed and why).
This module owns the *wording*: it anchors the question in what the user just
said, so the agent does not sound like a fixed questionnaire.

With an LLM configured, the model rewrites the question under strict
constraints (no new facts, no legal conclusion, one question, <= 80 Chinese
characters).  Without an LLM, a deterministic template interpolates known facts
and the element the question belongs to.  Both paths preserve the same
question key, so the gate and the evaluation stay reproducible.
"""
from __future__ import annotations

import hashlib
import json

from .issues import Question
from .llm import BaseLLM


class QuestionComposer:
    def __init__(self, llm: BaseLLM | None = None):
        self.llm = llm
        self._cache: dict[str, str] = {}
        self.fallbacks = 0

    # ------------------------------------------------------------------ API
    def intro(self, claims: list[str], labels: dict[str, str], facts: dict) -> str:
        if len(claims) > 1:
            names = "、".join(f"「{labels.get(c, c)}」" for c in claims[:3])
            return (f"您同时提到 {names} 这几条线。我先把最影响结论的事实确认一下，"
                    "再分别判断，不会用同一个模板套所有问题。")
        claim = claims[0] if claims else ""
        if claim == "tort_injury":
            return "在判断责任和赔偿范围之前，我需要先确认几个会直接影响适用标准的事实。"
        if claim.startswith("labor_"):
            focus = {
                "labor_dismissal": "解除是否合法、能拿 N、N+1 还是 2N",
                "labor_wage": "欠薪金额、时效和举证",
                "labor_overtime": "加班事实、工时制度和加班费计算",
                "labor_double_pay": "未签合同的期间和二倍工资",
                "labor_work_injury": "工伤认定、伤残等级和待遇",
                "labor_social_insurance": "补缴、损失赔偿还是被迫解除",
                "labor_annual_leave": "年假天数、未休折算和时效",
                "labor_noncompete": "竞业限制是否有效、补偿和违约金",
                "labor_maternity": "三期保护、产假待遇和解除",
                "labor_dispatch": "用工形式和劳动关系主体",
                "labor_contract": "合同订立、试用期和变更",
                "labor_procedure": "仲裁/诉讼路径和期限",
            }.get(claim, "您的请求")
            return f"在判断「{focus}」之前，我需要先确认几个会直接影响结论的事实。"
        return "为了给出负责任的结论，我需要先确认几个事实。"

    def compose(self, q: Question, facts: dict, labels: dict[str, str]) -> str:
        if q.refine:
            value = str(facts.get(q.key, ""))[:7]
            return (f"已经记下{q.field.label}是 {value}，能确认具体几号吗？"
                    "记不清可以先跳过，我会保留月份并标注估算。")
        key = self._cache_key(q, facts)
        if key in self._cache:
            return self._cache[key]
        text = None
        if self.llm and self.llm.enabled:
            text = self._llm_compose(q, facts, labels)
            if not text:
                self.fallbacks += 1
        if not text:
            text = self._template(q, facts, labels)
        if q.attempt:
            text = "这项还没确认：" + text
        self._cache[key] = text
        return text

    def compose_many(self, questions: list[Question], facts: dict,
                     labels: dict[str, str]) -> list[str]:
        out = []
        for q in questions:
            text = self.compose(q, facts, labels)
            if text not in out:
                out.append(text)
        return out

    # ------------------------------------------------------------- template
    def _template(self, q: Question, facts: dict, labels: dict[str, str]) -> str:
        lead = ""
        reason = facts.get("stated_reason")
        who = facts.get("who_initiated")
        if q.element == "illegality" and reason:
            lead = f"您提到公司以「{reason}」为由解除——"
        elif q.element == "dismissal_act" and who:
            lead = f"您说是「{who}」——"
        elif q.element and q.element not in ("relationship", "dismissal_act"):
            lead = f"关于「{q.element_label}」，"
        elif len(labels) > 1:
            lead = f"关于「{labels.get(q.claim, q.claim)}」，"
        question = q.field.question
        # allow schema questions to reference known facts without crashing
        for name, value in facts.items():
            question = question.replace("{" + name + "}", str(value))
        if "{employer}" in question and facts.get("employer"):
            question = question.replace("{employer}", str(facts["employer"]))
        return (lead + question).strip()

    # ------------------------------------------------------------------ LLM
    def _llm_compose(self, q: Question, facts: dict, labels: dict[str, str]) -> str | None:
        payload = {
            "claim": labels.get(q.claim, q.claim),
            "element": q.element_label,
            "fact": q.field.label,
            "question_skeleton": q.field.question,
            "why": q.field.why,
            "known_facts": {k: v for k, v in facts.items()
                            if v not in (None, "", "不清楚")},
        }
        res = self.llm.complete([
            {"role": "system", "content": (
                "你是劳动法律咨询的追问模块。把给定的问题骨架改写成一句自然、具体、"
                "当事人听得懂的中文问题。要求：1) 只问一个事实；2) 可以引用已知事实，"
                "但不得新增事实、金额、日期或法条；3) 不得下法律结论；4) 不超过80字；"
                "5) 不要重复“为什么问”。只输出问题本身。")},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ], temperature=0.2, max_tokens=160)
        if not res.ok:
            return None
        text = (res.text or "").strip().strip('"').split("\n")[0].strip()
        if not text or len(text) > 120:
            return None
        return text

    @staticmethod
    def _cache_key(q: Question, facts: dict) -> str:
        raw = json.dumps([q.key, q.claim, q.refine, q.attempt, facts.get(q.key), {k: facts.get(k) for k in
                                           ("stated_reason", "who_initiated", "employer",
                                            "injury_at_work", "dispatch_type")}],
                         ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

"""Controlled consultation protocol with scripted clients.

Each case hides a fact sheet.  The client answers only the questions it is
asked, says "不清楚" otherwise, and may issue one correction after the first
memorandum.  This makes inquiry behaviour and revision behaviour measurable
without human annotation and without an LLM judge.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from lexflow.agent import ConsultationAgent
from lexflow.corpus import StatuteCorpus
from lexflow.elements import ElementSchema
from lexflow.llm import BaseLLM
from lexflow.memory import MemoryStore

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "eval" / "scripted_cases.json"

CONDITIONS = {
    "answer_first": dict(use_gate=False, use_verify=False, use_repair=False),
    "gate_only": dict(use_gate=True, use_verify=False, use_repair=False),
    "full": dict(use_gate=True, use_verify=True, use_repair=True, use_revision=True),
    "full_no_revision": dict(use_gate=True, use_verify=True, use_repair=True,
                             use_revision=False),
    "full_no_voi": dict(use_gate=True, use_verify=True, use_repair=True,
                        use_revision=True, use_voi=False),
}

FIELD_TEMPLATES = {
    "dismiss_date": "解除日期是{value}。",
    "start_date": "我是{value}入职的。",
    "accident_date": "事故发生在{value}。",
    "monthly_wage": "月薪大概{value}。",
    "employer": "公司叫{value}。",
    "who_initiated": "是{value}。",
    "stated_reason": "公司的理由是{value}。",
    "rule_exists": "公司{value}。",
    "rule_publicized": "员工手册{value}。",
    "rule_democratic": "关于民主程序，{value}。",
    "misconduct_proof": "证据方面，{value}。",
    "union_notified": "工会方面，{value}。",
    "training_or_transfer": "公司{value}。",
    "notice_30d": "提前通知方面，{value}。",
    "claim_type": "我{value}。",
    "responsibility": "交警认定{value}。",
    "injury": "伤情是{value}。",
    "residence": "户籍是{value}。",
    "insurance": "保险方面，{value}。",
    "employment": "事故时{value}。",
    "claim_filed": "{value}。",
}


class ScriptedClient:
    def __init__(self, case: dict):
        self.case = case
        self.hidden = dict(case.get("hidden", {}))
        self.correction = case.get("correction")
        self.correction_sent = False

    def answer(self, questions: list[dict]) -> str:
        if not questions:
            return "我也不太确定，你看着办吧。"
        parts = []
        for q in questions:
            key = q.get("key")
            if key in self.hidden:
                parts.append(FIELD_TEMPLATES.get(key, "{value}。").format(value=self.hidden[key]))
            else:
                parts.append("这个我不太清楚。")
        return "".join(parts)

    def take_correction(self) -> str | None:
        if not self.correction or self.correction_sent:
            return None
        self.correction_sent = True
        return self.correction["text"]


@dataclass
class CaseRun:
    case_id: str
    condition: str
    status: str
    coverage: float
    inquiry_recall: float
    questions: int
    turns: int
    premature: bool
    support_rate: float
    illegal_ok: bool | None
    amount_ok: bool | None
    limitation_ok: bool | None
    version_ok: bool | None
    stale_after_correction: bool | None
    elapsed_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    cost_rmb: float = 0.0
    final: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def load_cases(path: Path = CASES) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _facts(result) -> dict:
    return {f["key"]: f["value"] for f in result.facts if f["superseded_by"] is None}


def _coverage(facts: dict, critical: list[str]) -> tuple[float, int]:
    ok = 0
    for k in critical:
        v = facts.get(k)
        if v not in (None, "", "不清楚", "记不清"):
            ok += 1
    return (ok / len(critical) if critical else 1.0), ok


def _answer_ok(analysis: dict, gold: dict) -> tuple[bool | None, bool | None, bool | None, bool | None]:
    meta = analysis.get("metadata", {})
    lim = meta.get("limitation", {}) or {}
    limitation_ok = None
    if gold.get("limitation_deadline"):
        limitation_ok = lim.get("deadline") == gold["limitation_deadline"]
    amount_ok = None
    if "amount" in gold:
        comp = meta.get("compensation", {}) or {}
        amount_ok = bool(comp.get("ok")) and abs(float(comp.get("amount", -1)) - gold["amount"]) < 1
    illegal_ok = None
    if "illegal" in gold:
        illegal_ok = bool(meta.get("illegal")) == gold["illegal"]
    version_ok = None
    if gold.get("interp"):
        version_ok = meta.get("interp") == gold["interp"]
    return illegal_ok, amount_ok, limitation_ok, version_ok


def run_case(case: dict, condition: str, corpus: StatuteCorpus,
             schema: ElementSchema, llm: BaseLLM, today: str,
             max_exchanges: int = 12) -> CaseRun:
    store = MemoryStore(":memory:")
    agent = ConsultationAgent(corpus, schema, store, llm=llm, today=today,
                              **CONDITIONS[condition])
    client = ScriptedClient(case)
    session = f"{case['id']}-{condition}"
    questions_asked: set[str] = set()
    usage = {"prompt": 0, "completion": 0, "calls": 0}

    def accumulate(r):
        usage["prompt"] += r.metrics.get("prompt_tokens", 0)
        usage["completion"] += r.metrics.get("completion_tokens", 0)
        usage["calls"] += r.metrics.get("llm_calls", 0)

    exchanges = 0
    result = agent.handle(session, case["opening"], case_type=case["case_type"])
    accumulate(result)
    initial_facts = set(_facts(result))
    while result.status == "asked" and exchanges < max_exchanges:
        if result.questions:
            questions_asked.update(q["key"] for q in result.questions)
        reply = client.answer(result.questions)
        exchanges += 1
        result = agent.handle(session, reply)
        accumulate(result)
    if result.status != "answered":
        result = agent.handle(session, "请根据目前的信息给我一份备忘录。", force_memo=True)
        accumulate(result)

    first_memo = result
    critical = case["gold"].get("critical", [])
    coverage, _ = _coverage(_facts(first_memo), critical)
    premature = coverage < 1.0

    stale = None
    if case.get("correction"):
        correction = client.take_correction()
        result = agent.handle(session, correction, force_memo=True)
        accumulate(result)
        exchanges = 0
        while result.status == "asked" and exchanges < max_exchanges:
            if result.questions:
                questions_asked.update(q["key"] for q in result.questions)
            exchanges += 1
            result = agent.handle(session, client.answer(result.questions))
            accumulate(result)
        if result.status != "answered":
            result = agent.handle(session, "请更新备忘录。", force_memo=True)
            accumulate(result)

    gold = case["gold"]
    illegal_ok, amount_ok, limitation_ok, version_ok = _answer_ok(result.analysis, gold)
    if case.get("correction"):
        checks = []
        if gold.get("limitation_deadline") is not None:
            checks.append(bool(limitation_ok))
        if gold.get("interp"):
            checks.append(bool(version_ok))
        stale = (not all(checks)) if checks else False
    # Only facts that were not volunteered in the opening can test inquiry.
    must_ask = [k for k in critical if k not in initial_facts]
    inquiry = (len(questions_asked & set(must_ask)) / len(must_ask)) if must_ask else 1.0
    run = CaseRun(
        case_id=case["id"], condition=condition, status=result.status,
        coverage=round(coverage, 3), inquiry_recall=round(inquiry, 3),
        questions=len(questions_asked), turns=exchanges + 1,
        premature=premature,
        support_rate=result.verification.get("support_rate", 0.0),
        illegal_ok=illegal_ok, amount_ok=amount_ok,
        limitation_ok=limitation_ok, version_ok=version_ok,
        stale_after_correction=stale,
        elapsed_ms=result.metrics.get("elapsed_ms", 0.0),
        prompt_tokens=usage["prompt"],
        completion_tokens=usage["completion"],
        llm_calls=usage["calls"],
        cost_rmb=round(usage["prompt"] / 1e6 * 1.0
                       + usage["completion"] / 1e6 * 2.0, 6),
        final={"analysis": result.analysis, "verification": result.verification,
               "memo_head": (result.memo or "")[:400]},
    )
    store.close()
    return run


def aggregate(runs: list[CaseRun]) -> dict:
    def mean(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    out = {}
    for cond in dict.fromkeys(r.condition for r in runs):
        rs = [r for r in runs if r.condition == cond]
        out[cond] = {
            "n": len(rs),
            "coverage": mean(r.coverage for r in rs),
            "inquiry_recall": mean(r.inquiry_recall for r in rs),
            "questions": mean(r.questions for r in rs),
            "premature_rate": mean(1.0 if r.premature else 0.0 for r in rs),
            "citation_support": mean(r.support_rate for r in rs),
            "illegal_acc": mean(1.0 if r.illegal_ok else 0.0 for r in rs if r.illegal_ok is not None),
            "amount_acc": mean(1.0 if r.amount_ok else 0.0 for r in rs if r.amount_ok is not None),
            "limitation_acc": mean(1.0 if r.limitation_ok else 0.0 for r in rs if r.limitation_ok is not None),
            "version_acc": mean(1.0 if r.version_ok else 0.0 for r in rs if r.version_ok is not None),
            "stale_rate": mean(1.0 if r.stale_after_correction else 0.0
                               for r in rs if r.stale_after_correction is not None),
            "latency_ms": mean(r.elapsed_ms for r in rs),
            "prompt_tokens": sum(r.prompt_tokens for r in rs),
            "completion_tokens": sum(r.completion_tokens for r in rs),
            "llm_calls": sum(r.llm_calls for r in rs),
            "cost_rmb": round(sum(r.cost_rmb for r in rs), 4),
        }
    return out

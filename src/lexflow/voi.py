"""Value-of-information (VOI) question selection.

Static priority answers "which fact is legally important"; it does not answer
"which question will actually change the conclusion now".  This module
approximates the latter:

* take the next frontier questions;
* for each, enumerate plausible answers (enum options, a few numbers/dates);
* run the deterministic rule layer on each hypothetical fact sheet;
* count how many *distinct outcomes* the question can distinguish.

A question that cannot change any outcome gets a low VOI even if its static
priority is high; a question that flips "2N vs no compensation" gets a high
one.  This is a lightweight, inspectable active-interrogation heuristic — not a
full Bayesian belief update.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import rules
from .issues import Question


@dataclass
class VOI:
    key: str
    distinct: int
    gain: float
    reason: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _outcome_signature(claims: list[str], facts: dict, today: str) -> tuple:
    try:
        analysis = rules.analyse_many(claims, facts, today, revision=0)
    except Exception:
        return ("error",)
    meta = analysis.metadata or {}
    per = meta.get("per_claim") or {}
    sig = []
    for claim in claims:
        m = per.get(claim) or {}
        lim = m.get("limitation") or {}
        expired = bool(lim.get("expired"))
        if claim == "labor_dismissal":
            comp = m.get("compensation") or {}
            amount = (round(float(comp.get("amount") or 0), -3)
                      if comp.get("ok") else None)
            sig.append(("dismissal", bool(m.get("illegal")),
                        comp.get("multiplier") if comp.get("ok") else None,
                        amount, expired))
        elif claim == "tort_injury":
            sig.append(("tort", m.get("interp"), expired))
        else:
            calc = m.get("calculation") or {}
            amount = round(float(calc.get("amount") or 0), -3) if calc.get("ok") else None
            sig.append((claim, amount, expired))
    return tuple(sig)


def _values(field, today: str) -> list:
    if field.options:
        return [o for o in field.options if o not in ("不清楚", "说不清", "记不清")][:6]
    if field.type == "number":
        table = {
            "monthly_wage": [0, 5000, 15000, 30000],
            "wage_owed": [0, 10000, 50000],
            "overtime_hours_weekday": [0, 10, 36],
            "overtime_hours_rest": [0, 8, 32],
            "overtime_hours_holiday": [0, 3, 12],
            "no_contract_months": [0, 6, 11],
            "cumulative_work_years": [1, 12, 25],
            "noncompete_months": [0, 12, 24],
        }
        return table.get(field.key, [0, 10000])
    if field.type == "date":
        d = date.fromisoformat(today)
        return [d.isoformat(), (d - timedelta(days=730)).isoformat(),
                (d - timedelta(days=1825)).isoformat()]
    return []


class ScenarioVOI:
    def __init__(self, today: str):
        self.today = today

    def score(self, questions: list[Question], claims: list[str],
              facts: dict) -> dict[str, VOI]:
        out: dict[str, VOI] = {}
        for q in questions[:12]:
            values = _values(q.field, self.today)
            if not values:
                continue
            sigs = set()
            for value in values:
                hypothetical = dict(facts)
                hypothetical[q.key] = value
                sigs.add(_outcome_signature(claims, hypothetical, self.today))
            distinct = len(sigs)
            if distinct <= 1:
                out[q.key] = VOI(q.key, distinct, 0.0,
                                 "回答这个问题大概率不会改变当前结论")
                continue
            # static legal importance still matters, but only as a tie-breaker
            weight = max(0.2, q.field.priority / 100.0)
            gain = (distinct - 1) * weight
            out[q.key] = VOI(
                q.key, distinct, round(gain, 3),
                f"回答后可在 {distinct} 种可能结果之间区分（其余事实不变）")
        return out

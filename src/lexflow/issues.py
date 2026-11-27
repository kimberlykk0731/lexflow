"""Element hierarchy traversal and adaptive question selection.

A claim is not a flat checklist.  It is a small tree:

    claim (请求权)
      └─ element (要件)
           ├─ fact (要件事实)
           └─ proof (证据)

``requires`` on an element can switch a whole branch off.  For example, when
the user says "我是自己辞职的", the illegal-dismissal branch (规章制度、工会、
2N) is no longer asked; the agent moves to the 被迫解除/经济补偿 branch.

The traversal also produces the reasoning chain shown in the memo, so the user
can see *why* each question was asked and which element is still open.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .elements import ElementSchema, Field, _match_all


@dataclass
class Question:
    key: str
    field: Field
    claim: str
    element: str
    element_label: str
    score: float
    reason: str = ""


@dataclass
class ElementState:
    id: str
    label: str
    status: str                 # satisfied | partial | unknown | blocked
    facts: list[dict] = field(default_factory=list)
    why: str = ""
    proof: list[str] = field(default_factory=list)
    children: list["ElementState"] = field(default_factory=list)


def _cond_status(facts: dict, cond: dict | None) -> bool | None:
    """True/False, or None when a required fact is still unknown.

    Unknown is treated as "branch still possible" so the agent asks instead of
    silently skipping a potentially relevant element.
    """
    if not cond:
        return True
    unknown = False
    for key, expected in cond.items():
        base = key.split("__", 1)[0]
        value = facts.get(base)
        if value in (None, "", "不清楚", "记不清", "说不清", "不知道", "不方便说"):
            unknown = True
            continue
        if not _match_all(facts, {key: expected}):
            return False
    return None if unknown else True


class IssueTree:
    def __init__(self, schema: ElementSchema):
        self.schema = schema

    def _elements(self, claim: str) -> list[dict]:
        elements = self.schema.elements(claim)
        listed = {key for el in elements for key in el.get("facts", [])}
        missing = [f.key for f in self.schema.fields(claim)
                   if f.key not in listed and (f.critical or f.critical_if)]
        if missing:
            elements = elements + [{"id": "additional_facts", "label": "补充事实",
                                    "facts": missing, "essential": True}]
        return elements

    # ------------------------------------------------------------ traversal
    def active_elements(self, claim: str, facts: dict) -> list[tuple[dict, bool | None]]:
        out = []
        for el in self._elements(claim):
            status = _cond_status(facts, el.get("requires"))
            if status is False:
                out.append((el, False))
            else:
                out.append((el, status))
        return out

    def element_state(self, claim: str, el: dict, facts: dict) -> ElementState:
        rows = []
        known = 0
        for key in el.get("facts", []):
            f = self.schema.field(claim, key)
            if not f:
                continue
            value = facts.get(key)
            is_known = value not in (None, "", "不清楚", "记不清", "说不清", "不知道")
            # Unknown, non-critical facts are not "open elements": they are
            # simply not needed on this branch (e.g. training/transfer when the
            # stated reason is not "incompetence").
            if not is_known and not self.schema.is_critical(f, facts, claim):
                continue
            known += 1 if is_known else 0
            rows.append({"key": key, "label": f.label,
                         "value": value if is_known else "",
                         "known": is_known,
                         "critical": self.schema.is_critical(f, facts, claim)})
        cond = _cond_status(facts, el.get("requires"))
        if cond is False:
            status = "blocked"
        elif known == len(rows) and rows:
            status = "satisfied"
        elif known == 0:
            status = "unknown"
        else:
            status = "partial"
        return ElementState(id=el.get("id", ""), label=el.get("label", ""),
                            status=status, facts=rows, why=el.get("why", ""),
                            proof=el.get("proof", []))

    def chain(self, claims: list[str], facts: dict) -> list[dict]:
        out = []
        for claim in claims:
            elements = [self.element_state(claim, el, facts)
                        for el in self._elements(claim)]
            out.append({
                "claim": claim,
                "label": self.schema.label(claim),
                "summary": self.schema.summary(claim),
                "basis": self.schema.claim_basis(claim),
                "remedy": self.schema.remedy(claim),
                "elements": [
                    {"id": e.id, "label": e.label, "status": e.status,
                     "why": e.why, "proof": e.proof,
                     "facts": e.facts}
                    for e in elements
                ],
            })
        return out

    # ------------------------------------------------------------- frontier
    def frontier(self, claims: list[str], facts: dict,
                 asked: list[str] | None = None,
                 precisions: dict[str, str] | None = None) -> list[Question]:
        asked = set(asked or [])
        precisions = precisions or {}
        seen: dict[str, Question] = {}
        for claim in claims:
            for el, active in self.active_elements(claim, facts):
                if active is False:
                    continue
                for key in el.get("facts", []):
                    f = self.schema.field(claim, key)
                    if not f or f.key in asked:
                        continue
                    if not self.schema.is_critical(f, facts, claim):
                        # still ask a non-critical fact if an essential element
                        # has nothing else left? No: keep the gate to criticals.
                        continue
                    value = facts.get(f.key)
                    if value not in (None, "", "不清楚", "记不清", "说不清", "不知道"):
                        # A date known only to the month is still worth one
                        # refinement question (it changes limitation / years).
                        if precisions.get(f.key) != "month":
                            continue
                    q = self._score(claim, el, f, facts)
                    if precisions.get(f.key) == "month":
                        q.score += 30
                    old = seen.get(f.key)
                    if old is None or q.score > old.score:
                        seen[f.key] = q
        return sorted(seen.values(), key=lambda q: -q.score)

    def _score(self, claim: str, el: dict, f: Field, facts: dict) -> Question:
        score = float(f.priority)
        if el.get("essential", True):
            score += 6
        # time anchors are the first thing a lawyer pins down
        if f.key in ("dismiss_date", "injury_date", "accident_date", "wage_period"):
            score += 12
        # once the core facts exist, ask about limitation/procedure
        if f.key in ("arbitration_filed", "deadline_aware") and len(facts) >= 3:
            score += 18
        # do not let an optional claim crowd out the primary one
        if f.claim and f.claim != claim:
            score -= 3
        return Question(key=f.key, field=f, claim=claim,
                        element=el.get("id", ""), element_label=el.get("label", ""),
                        score=score, reason=f.why)

    def next_questions(self, claims: list[str], facts: dict, n: int = 2,
                       asked: list[str] | None = None,
                       ask_counts: dict[str, int] | None = None,
                       precisions: dict[str, str] | None = None,
                       voi: dict | None = None) -> list[Question]:
        counts = ask_counts or {}
        # Do not exclude previously asked keys: a user may ignore a question.
        # Instead, cap how many times the same key is asked.
        frontier = [q for q in self.frontier(claims, facts, precisions=precisions)
                    if counts.get(q.key, 0) < 2]
        for q in frontier:
            q.score -= 25 * counts.get(q.key, 0)
            if voi and q.key in voi:
                q.score += voi[q.key].gain * 20
        frontier.sort(key=lambda q: -q.score)
        out: list[Question] = []
        for q in frontier[:n]:
            out.append(q)
        return out

    # --------------------------------------------------------------- coverage
    def coverage(self, claims: list[str], facts: dict) -> dict:
        total = known = 0
        for claim in claims:
            for el, active in self.active_elements(claim, facts):
                if active is False:
                    continue
                for key in el.get("facts", []):
                    f = self.schema.field(claim, key)
                    if not f or not self.schema.is_critical(f, facts, claim):
                        continue
                    total += 1
                    if facts.get(key) not in (None, "", "不清楚", "记不清", "说不清", "不知道"):
                        known += 1
        return {"known": known, "total": total,
                "rate": round(known / total, 4) if total else 1.0}

    # ------------------------------------------------------------ next steps
    def proof_checklist(self, claims: list[str], facts: dict) -> list[str]:
        items: list[str] = []
        for claim in claims:
            for el in self.schema.elements(claim):
                if _cond_status(facts, el.get("requires")) is False:
                    continue
                for p in el.get("proof", []):
                    if p not in items:
                        items.append(p)
        return items

"""Fact catalog, claim schemas, element hierarchy and sufficiency gating.

Version 2 splits the old flat "one questionnaire per cause of action" into:

* a **shared fact catalog** (``facts``) — one canonical question per fact;
* **claims** (``claims``) — labour claims that reference facts, with per-claim
  criticality/priority and a hierarchy of **elements** (claim -> element ->
  fact -> proof).

The agent can therefore run several claims at once (e.g. dismissal + unpaid
wages), and a conditional element disappears from the question queue when its
``requires`` condition is false.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as dc_field
from datetime import date
from pathlib import Path

from .config import ELEMENTS


@dataclass
class Field:
    key: str
    label: str
    question: str
    type: str
    critical: bool
    priority: int
    options: list[str] = dc_field(default_factory=list)
    why: str = ""
    basis: list[str] = dc_field(default_factory=list)
    critical_if: list[dict] = dc_field(default_factory=list)
    critical_if_date_before: str | None = None
    proof: list[str] = dc_field(default_factory=list)
    claim: str = ""
    element: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Field":
        return cls(
            key=d["key"], label=d["label"], question=d["question"], type=d["type"],
            critical=d.get("critical", False), priority=d.get("priority", 0),
            options=d.get("options", []), why=d.get("why", ""),
            basis=d.get("basis", []), critical_if=d.get("critical_if", []),
            critical_if_date_before=d.get("critical_if_date_before"),
            proof=d.get("proof", []),
        )

    def copy(self) -> "Field":
        return Field(**self.__dict__)


class ElementSchema:
    def __init__(self, path: Path = ELEMENTS):
        self.raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.version = self.raw.get("version", 1)
        if "claims" in self.raw and "facts" in self.raw:
            self._load_v2()
        else:
            self._load_v1()

    # ------------------------------------------------------------- loaders
    def _load_v1(self) -> None:
        """Backward compatibility with the old case_types format."""
        self.fact_defs: dict[str, dict] = {}
        self.claims: dict[str, dict] = {}
        self.out_of_scope: dict[str, dict] = {}
        for ctype, spec in self.raw["case_types"].items():
            fields = []
            for fd in spec["fields"]:
                self.fact_defs.setdefault(fd["key"], {k: v for k, v in fd.items()
                                                      if k not in ("critical", "priority",
                                                                   "critical_if",
                                                                   "critical_if_date_before")})
                fields.append({k: fd[k] for k in ("key", "critical", "priority", "why", "basis")
                               if k in fd} | {
                    "critical_if": fd.get("critical_if", []),
                    "critical_if_date_before": fd.get("critical_if_date_before"),
                })
            self.claims[ctype] = {
                "label": spec["label"], "matter": "labor" if "labor" in ctype else "tort",
                "stage": "", "aliases": spec.get("aliases", []),
                "law_hints": spec.get("law_hints", []),
                "default_as_of": spec.get("default_as_of", "dismiss_date"),
                "summary": "", "priority": 50, "fields": fields, "elements": [],
            }
        self._fields = {c: {f["key"]: self._merge_field(c, f) for f in s["fields"]}
                        for c, s in self.claims.items()}

    def _load_v2(self) -> None:
        self.fact_defs = self.raw["facts"]
        self.claims = self.raw["claims"]
        self.out_of_scope = self.raw.get("out_of_scope", {})
        self._fields: dict[str, dict[str, Field]] = {}
        for cid, spec in self.claims.items():
            fields = {}
            for fd in spec["fields"]:
                fields[fd["key"]] = self._merge_field(cid, fd)
            # facts referenced by elements but not declared are still available
            for el in spec.get("elements", []):
                for key in el.get("facts", []):
                    if key not in fields and key in self.fact_defs:
                        fields[key] = self._merge_field(cid, {"key": key, "critical": False,
                                                              "priority": 30})
            self._fields[cid] = fields

    def _merge_field(self, claim: str, spec: dict) -> Field:
        key = spec["key"]
        base = dict(self.fact_defs.get(key, {}))
        merged = {**base, **{k: v for k, v in spec.items() if v is not None}}
        merged["key"] = key
        if "type" not in merged:
            merged["type"] = "text"
        f = Field.from_dict(merged)
        f.claim = claim
        return f

    # ---------------------------------------------------------------- lookup
    def types(self) -> list[str]:
        return list(self.claims)

    def matters(self) -> list[str]:
        return sorted({c.get("matter", "") for c in self.claims.values() if c.get("matter")})

    def claims_for_matter(self, matter: str) -> list[str]:
        return [c for c, s in self.claims.items() if s.get("matter") == matter]

    def label(self, case_type: str) -> str:
        return self.claims.get(case_type, {}).get("label", case_type)

    def stage(self, case_type: str) -> str:
        return self.claims.get(case_type, {}).get("stage", "")

    def summary(self, case_type: str) -> str:
        return self.claims.get(case_type, {}).get("summary", "")

    def law_hints(self, case_type: str | list[str]) -> list[str]:
        claims = [case_type] if isinstance(case_type, str) else case_type
        hints: list[str] = []
        for c in claims:
            hints.extend(self.claims.get(c, {}).get("law_hints", []))
        return list(dict.fromkeys(hints))

    def default_as_of(self, case_type: str) -> str:
        return self.claims.get(case_type, {}).get("default_as_of", "dismiss_date")

    def aliases(self, case_type: str) -> list[str]:
        return self.claims.get(case_type, {}).get("aliases", [])

    def fields(self, case_type: str | list[str]) -> list[Field]:
        claims = [case_type] if isinstance(case_type, str) else case_type
        out: dict[str, Field] = {}
        for c in claims:
            for key, f in self._fields.get(c, {}).items():
                old = out.get(key)
                if old is None or f.priority > old.priority:
                    out[key] = f
        return sorted(out.values(), key=lambda f: -f.priority)

    def field(self, case_type: str, key: str) -> Field | None:
        f = self._fields.get(case_type, {}).get(key)
        if f:
            return f
        if key in self.fact_defs and case_type in self.claims:
            return self._merge_field(case_type, {"key": key, "critical": False, "priority": 0})
        return None

    def declares(self, claim: str, key: str) -> bool:
        return key in self._fields.get(claim, {})

    def field_any(self, key: str) -> Field | None:
        if key in self.fact_defs:
            return Field.from_dict({"key": key, **self.fact_defs[key]})
        for c in self.claims:
            f = self._fields.get(c, {}).get(key)
            if f:
                return f
        return None

    def elements(self, case_type: str) -> list[dict]:
        return self.claims.get(case_type, {}).get("elements", [])

    # ------------------------------------------------------------ classify
    def classify(self, text: str) -> list[tuple[str, int]]:
        text = (text or "").lower()
        scores = []
        for ctype, spec in self.claims.items():
            score = sum(1 for a in spec.get("aliases", []) if a.lower() in text)
            scores.append((ctype, score))
        scores.sort(key=lambda x: -x[1])
        return scores

    # ----------------------------------------------------------- sufficiency
    def is_critical(self, field: Field, facts: dict, case_type: str) -> bool:
        if field.critical_if:
            matched = any(_match_all(facts, cond) for cond in field.critical_if)
            if not matched:
                return False
            if field.critical_if_date_before:
                anchor = facts.get("accident_date") or facts.get("dismiss_date")
                if anchor and str(anchor) >= field.critical_if_date_before:
                    return False
            return True
        return field.critical

    def missing(self, case_type: str | list[str], facts: dict) -> list[Field]:
        """Missing critical facts across one or several active claims."""
        claims = [case_type] if isinstance(case_type, str) else list(case_type)
        seen: dict[str, Field] = {}
        for c in claims:
            for f in self.fields(c):
                if not self.is_critical(f, facts, c):
                    continue
                if _empty(facts.get(f.key)):
                    if f.key not in seen or f.priority > seen[f.key].priority:
                        copy = f.copy()
                        copy.claim = c
                        seen[f.key] = copy
        return sorted(seen.values(), key=lambda f: -f.priority)

    def unknown(self, case_type: str | list[str], facts: dict) -> list[Field]:
        claims = [case_type] if isinstance(case_type, str) else list(case_type)
        out = []
        for f in self.fields(claims):
            if self.is_critical(f, facts, f.claim) and _is_unknown(facts.get(f.key)):
                out.append(f)
        return out

    def ready(self, case_type: str | list[str], facts: dict) -> bool:
        return not self.missing(case_type, facts)

    def next_questions(self, case_type: str | list[str], facts: dict, n: int = 2,
                       asked: set[str] | None = None) -> list[Field]:
        asked = asked or set()
        missing = [f for f in self.missing(case_type, facts) if f.key not in asked]
        return missing[:n]

    # ------------------------------------------------------------ normalize
    def normalize(self, field: Field, raw) -> str | float | None:
        if raw is None:
            return None
        if field.type == "number":
            return _to_number(raw)
        if field.type == "date":
            return _to_date(raw)
        text = str(raw).strip()
        if field.type == "enum" and field.options:
            if text in field.options:
                return text
            for opt in field.options:
                if opt in text or text in opt:
                    return opt
            for opt in field.options:
                core = re.sub(r"[（(].*?[）)]", "", opt)
                if core and core in text:
                    return opt
            return field.options[-1]
        return text


# --------------------------------------------------------------- conditions
def _match_all(facts: dict, cond: dict) -> bool:
    return all(_match_one(facts, key, expected) for key, expected in cond.items())


def _match_one(facts: dict, key: str, expected) -> bool:
    op = None
    if "__" in key:
        key, op = key.split("__", 1)
    value = facts.get(key)
    if op == "in":
        return value in (expected or [])
    if op == "not_in":
        return value not in (expected or [])
    if op == "ne":
        return value is not None and value != expected
    if op == "exists":
        return bool(value) == bool(expected)
    if op == "before":
        return bool(value) and str(value) < str(expected)
    if op == "after":
        return bool(value) and str(value) > str(expected)
    if op == "gte":
        try:
            return float(value) >= float(expected)
        except (TypeError, ValueError):
            return False
    if op == "lte":
        try:
            return float(value) <= float(expected)
        except (TypeError, ValueError):
            return False
    return value == expected


def _match(value, expected) -> bool:
    return isinstance(value, str) and value == expected


UNKNOWN_VALUES = {"不清楚", "记不清", "说不清", "不知道", "未知", "不方便说"}


def _empty(v) -> bool:
    return v is None or (isinstance(v, str) and (not v.strip() or v in UNKNOWN_VALUES))


def _is_unknown(v) -> bool:
    return isinstance(v, str) and v in UNKNOWN_VALUES


def _to_number(raw) -> float | None:
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).replace(",", "").replace("，", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(万|w|k|千)?", text, re.I)
    if not m:
        return None
    value = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit in {"万", "w"}:
        value *= 10000
    elif unit in {"千", "k"}:
        value *= 1000
    return value


def _to_date(raw) -> str | None:
    if isinstance(raw, date):
        return raw.isoformat()
    text = str(raw)
    m = re.search(r"(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]?\s*(\d{1,2})?", text)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    day = int(m.group(3)) if m.group(3) else 1
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(text))
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

"""Element-of-claim schema and sufficiency gating.

The central design choice of LexFlow: a legal conclusion is only produced when
the facts required by the *elements of the claim* are present.  Missing
critical facts trigger a targeted question instead of a confident answer.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
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
    options: list[str]
    why: str
    basis: list[str]
    critical_if: list[dict]
    critical_if_date_before: str | None

    @classmethod
    def from_dict(cls, d: dict) -> "Field":
        return cls(
            key=d["key"], label=d["label"], question=d["question"], type=d["type"],
            critical=d.get("critical", False), priority=d.get("priority", 0),
            options=d.get("options", []), why=d.get("why", ""),
            basis=d.get("basis", []), critical_if=d.get("critical_if", []),
            critical_if_date_before=d.get("critical_if_date_before"),
        )


class ElementSchema:
    def __init__(self, path: Path = ELEMENTS):
        self.raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.case_types: dict[str, dict] = self.raw["case_types"]
        self._fields: dict[str, dict[str, Field]] = {}
        for ctype, spec in self.case_types.items():
            self._fields[ctype] = {f["key"]: Field.from_dict(f) for f in spec["fields"]}

    # ---------------------------------------------------------------- lookup
    def types(self) -> list[str]:
        return list(self.case_types)

    def label(self, case_type: str) -> str:
        return self.case_types[case_type]["label"]

    def law_hints(self, case_type: str) -> list[str]:
        return self.case_types[case_type].get("law_hints", [])

    def fields(self, case_type: str) -> list[Field]:
        return sorted(self._fields[case_type].values(), key=lambda f: -f.priority)

    def field(self, case_type: str, key: str) -> Field | None:
        return self._fields.get(case_type, {}).get(key)

    # ------------------------------------------------------------ classify
    def classify(self, text: str) -> list[tuple[str, int]]:
        text = (text or "").lower()
        scores = []
        for ctype, spec in self.case_types.items():
            score = sum(1 for a in spec.get("aliases", []) if a.lower() in text)
            scores.append((ctype, score))
        scores.sort(key=lambda x: -x[1])
        return scores

    # ----------------------------------------------------------- sufficiency
    def is_critical(self, field: Field, facts: dict, case_type: str) -> bool:
        if field.critical_if:
            matched = any(all(_match(facts.get(k), v) for k, v in cond.items())
                          for cond in field.critical_if)
            if not matched:
                return False
            if field.critical_if_date_before:
                anchor = facts.get("accident_date") or facts.get("dismiss_date")
                if anchor and str(anchor) >= field.critical_if_date_before:
                    return False
            return True
        return field.critical

    def missing(self, case_type: str, facts: dict) -> list[Field]:
        out = []
        for f in self.fields(case_type):
            if not self.is_critical(f, facts, case_type):
                continue
            if _empty(facts.get(f.key)):
                out.append(f)
        return out

    def unknown(self, case_type: str, facts: dict) -> list[Field]:
        out = []
        for f in self.fields(case_type):
            if self.is_critical(f, facts, case_type) and _is_unknown(facts.get(f.key)):
                out.append(f)
        return out

    def ready(self, case_type: str, facts: dict) -> bool:
        return not self.missing(case_type, facts)

    def next_questions(self, case_type: str, facts: dict, n: int = 2,
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


def _match(value, expected) -> bool:
    return isinstance(value, str) and value == expected


UNKNOWN_VALUES = {"不清楚", "记不清", "说不清", "不知道", "未知"}


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

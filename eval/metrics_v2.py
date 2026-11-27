"""Pure scoring functions. No calls to production rules or extraction."""
from __future__ import annotations

import math
import re
from collections import Counter

UNKNOWN = (None, "", "不清楚", "记不清", "不知道", "说不清")
MISSING = object()


def equal_value(actual, expected, tolerance: float = 0.01) -> bool:
    if actual is MISSING or actual is None or expected is None:
        return False
    if type(expected) is bool:
        return type(actual) is bool and actual == expected
    if isinstance(expected, (int, float)):
        if isinstance(actual, bool):
            return False
        try:
            value = float(str(actual).replace(",", ""))
            return math.isfinite(value) and abs(value - float(expected)) <= tolerance + 1e-9
        except (ValueError, TypeError):
            return False
    return re.sub(r"\s+", "", str(actual)) == re.sub(r"\s+", "", str(expected))


def active_facts(rows: list[dict]) -> dict:
    return {r["key"]: r["value"] for r in rows
            if r.get("superseded_by") is None and r.get("status") != "unknown"
            and r.get("value") not in UNKNOWN}


def ratio(n: int, d: int):
    return n / d if d else None


def fact_scores(actual: dict, disclosed: dict, hidden: dict, critical: list[str]) -> dict:
    known_truth = {k: v for k, v in disclosed.items() if v not in UNKNOWN}
    correct = {k for k, v in actual.items() if equal_value(v, known_truth.get(k, MISSING))}
    assessable = [k for k in critical if hidden.get(k) not in UNKNOWN]
    correct_critical = [k for k in assessable if k in correct]
    p, r = ratio(len(correct), len(actual)), ratio(len(correct), len(known_truth))
    return {"correct_coverage": ratio(len(correct_critical), len(assessable)),
            "critical_correct": len(correct_critical), "critical_n": len(assessable),
            "extraction_precision": p, "extraction_recall": r,
            "extraction_f1": 2 * (p or 0) * (r or 0) / (p + r) if p is not None and r is not None and p + r else 0.0,
            "incorrect_or_unsupported_keys": sorted(set(actual) - correct),
            "missing_or_wrong_critical": sorted(set(assessable) - set(correct_critical))}


def claim_scores(actual: list[str], expected: list[str]) -> dict:
    a, e = set(actual), set(expected)
    p, r = len(a & e) / len(a) if a else 0.0, len(a & e) / len(e) if e else 1.0
    return {"claim_precision": p, "claim_recall": r,
            "claim_f1": 2 * p * r / (p + r) if p + r else 0.0,
            "claim_exact": a == e}


def lookup(analysis: dict, claim: str, path: str):
    meta = analysis.get("metadata", {})
    if claim not in meta.get("claims", []) and claim not in meta.get("per_claim", {}) and analysis.get("case_type") != claim:
        return MISSING
    if path.startswith("finding:"):
        finding_id = path.split(":", 1)[1]
        return any(f.get("id") == finding_id for f in analysis.get("findings", []))
    if path.startswith("finding_text:") or path.startswith("finding_money:"):
        kind, finding_id = path.split(":", 1)
        finding = next((f for f in analysis.get("findings", []) if f.get("id") == finding_id), None)
        if not finding:
            return MISSING
        text = finding.get("conclusion", "")
        if kind == "finding_money":
            match = re.search(r"([\d,]+(?:\.\d+)?)\s*元", text)
            return float(match.group(1).replace(",", "")) if match else MISSING
        return text
    if path.startswith("gap_contains:"):
        return path.split(":", 1)[1] in "\n".join(analysis.get("gaps", []))
    per = meta.get("per_claim", {})
    if per:
        value = per.get(claim, MISSING)
    elif analysis.get("case_type") == claim:
        value = meta
    else:
        return MISSING
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value


def score_assertions(analysis: dict, gold: list[dict]) -> list[dict]:
    rows = []
    for spec in gold:
        value = lookup(analysis, spec["claim"], spec["path"])
        rows.append({**spec, "actual": None if value is MISSING else value,
                     "present": value is not MISSING,
                     "ok": ((str(spec["expected"]) in str(value)) if spec.get("match") == "contains" and value is not MISSING
                            else equal_value(value, spec["expected"], spec.get("tolerance", 0.01)))
                     if spec["applicable"] else None})
    return rows


def question_scores(keys: list[str], critical: list[str], opening_facts: dict) -> dict:
    # Denominator comes from annotated disclosure, never the agent's own extraction.
    required = set(critical) - set(opening_facts)
    counts = Counter(keys)
    return {"questions": len(keys), "unique_questions": len(counts),
            "repeat_questions": len(keys) - len(counts),
            "repeat_rate": ratio(len(keys) - len(counts), len(keys)),
            "inquiry_recall": ratio(len(set(keys) & required), len(required))}


def revision_score(before: dict, after: dict, gold_after: list[dict], corrected: dict,
                   final_facts: dict, disclosed: dict) -> dict:
    checks = score_assertions(after, gold_after)
    affected = [r for r in checks if r["applicable"] and set(r.get("depends", [])) & set(corrected)]
    unchanged = [r for r in checks if r["applicable"] and not set(r.get("depends", [])) & set(corrected)
                 and equal_value(lookup(before, r["claim"], r["path"]), r["expected"], r.get("tolerance", 0.01))]
    return {"corrected_facts_ok": all(equal_value(final_facts.get(k, MISSING), disclosed[k]) for k in corrected),
            "affected_checks": len(affected),
            "affected_outcomes_ok": all(r["ok"] for r in affected) if affected else None,
            "unaffected_checks": len(unchanged),
            "unaffected_preserved": all(r["ok"] for r in unchanged) if unchanged else None}

#!/usr/bin/env python3
"""Validate facts, gold reproducibility, splits and explicitly incomplete coverage."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from gen_cases import critical_keys, matches
from reference_oracle import reference_gold


def validate(data: dict, schema: dict) -> dict:
    errors, signatures = [], {}
    ids = set()
    today = data["today"]
    for case in data["cases"]:
        cid = case["id"]
        def err(message):
            errors.append(f"{cid}: {message}")
        if cid in ids:
            err("duplicate id")
        ids.add(cid)
        claims, hidden = case["claims_gold"], case["hidden"]
        if not claims or any(c not in schema["claims"] for c in claims):
            err("unknown claim")
            continue
        signature = hashlib.sha256(json.dumps([sorted(claims), hidden], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if signature in signatures:
            err(f"duplicate substantive facts with {signatures[signature]}")
        signatures[signature] = cid
        if case["split"] not in ("dev", "test"):
            err("invalid split")
        for key, value in hidden.items():
            spec = schema["facts"].get(key)
            if spec is None:
                err(f"unknown fact {key}")
                continue
            if value is None:
                continue  # Unavailable facts are intentionally retained.
            kind = spec["type"]
            if kind == "enum" and value not in spec["options"]:
                err(f"invalid enum {key}")
            if kind == "number" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                err(f"invalid number {key}")
            if kind == "date":
                try:
                    if date.fromisoformat(value) > date.fromisoformat(today):
                        err(f"future factual date {key}")
                except (ValueError, TypeError):
                    err(f"invalid ISO date {key}")
        if hidden.get("start_date") and hidden.get("dismiss_date") and hidden["start_date"] >= hidden["dismiss_date"]:
            err("employment date order")
        for key, value in case["opening_facts"].items():
            if hidden.get(key) != value:
                err(f"opening fact contradicts hidden {key}")
        if any(key not in hidden for key in case["critical"]):
            err("critical fact absent from sheet")
        if critical_keys(claims, hidden, schema) != case["critical"]:
            err("critical mask out of sync")
        try:
            if case["gold_before"] != reference_gold(case, hidden, today):
                err("independent gold_before not reproducible")
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            err(f"invalid reference input: {exc}")
        if hidden.get("overtime_exists") == "没有" and any(hidden.get(k, 0) for k in
                ("overtime_hours_weekday", "overtime_hours_rest", "overtime_hours_holiday")):
            err("no overtime but positive hours")
        correction = case.get("correction")
        if correction:
            key, old, new = correction["key"], correction["old"], correction["new"]
            if hidden.get(key) != old or old == new:
                err("invalid correction")
            after = {**hidden, key: new}
            field_spec = schema["facts"].get(key, {})
            if field_spec.get("type") == "enum" and new not in field_spec["options"]:
                err("invalid corrected enum")
            if field_spec.get("type") == "date":
                try:
                    if date.fromisoformat(new) > date.fromisoformat(today):
                        err("future corrected date")
                except (ValueError, TypeError):
                    err("invalid corrected ISO date")
            if after.get("start_date") and after.get("dismiss_date") and after["start_date"] >= after["dismiss_date"]:
                err("corrected employment date order")
            try:
                if case["gold_after"] != reference_gold(case, after, today):
                    err("independent gold_after not reproducible")
            except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                err(f"invalid corrected reference input: {exc}")
            if [s["expected"] for s in case["gold_before"]] == [s["expected"] for s in case["gold_after"]]:
                err("correction does not change any asserted outcome")
        # The opening is not generated from gold. Lexical/semantic leakage still needs review.
        if any(t in case["opening"] for t in ("gold", "标准答案", "隐藏事实")):
            err("literal answer leakage")
    branches = []
    for claim, spec in schema["claims"].items():
        if not claim.startswith("labor_"):
            continue
        for field in spec["fields"]:
            conds = field.get("critical_if")
            if not conds:
                continue
            true_cases, false_cases = [], []
            for case in data["cases"]:
                if claim not in case["claims_gold"]:
                    continue
                hit = any(matches(case["hidden"], cond) for cond in conds)
                (true_cases if hit else false_cases).append(case["id"])
            branches.append({"claim": claim, "field": field["key"], "true_cases": true_cases,
                             "false_cases": false_cases, "both_sides": bool(true_cases and false_cases)})
    return {"ok": not errors, "errors": errors, "n_cases": len(data["cases"]),
            "splits": dict(Counter(c["split"] for c in data["cases"])),
            "primary_claims": dict(Counter(c["primary_claim"] for c in data["cases"])),
            "tags": dict(Counter(t for c in data["cases"] for t in c["tags"])),
            "conditional_fields": len(branches), "both_sides_covered": sum(b["both_sides"] for b in branches),
            "branch_details": branches, "human_reviewed": sum(c["review"]["human_status"] == "approved" for c in data["cases"]),
            "coverage_scope": "critical_if predicates only; element.requires and temporal boundaries not fully covered"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=ROOT / "data/eval/labor_cases_v2.json")
    ap.add_argument("--out", type=Path, default=ROOT / "runs/bench_v2/validation.json")
    ap.add_argument("--require-human-review", action="store_true")
    args = ap.parse_args()
    data = json.loads(args.cases.read_text())
    schema = json.loads((ROOT / "data/elements.json").read_text())
    result = validate(data, schema)
    result["dataset_sha256"] = hashlib.sha256(args.cases.read_bytes()).hexdigest()
    if args.require_human_review and result["human_reviewed"] < 7:
        result["errors"].append("at least seven explicit human approvals required")
        result["ok"] = False
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "branch_details"}, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Cross-check production rules against independent gold; NEVER generate gold here."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lexflow.rules import analyse_many
from metrics_v2 import score_assertions


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=ROOT / "data/eval/labor_cases_v2.json")
    ap.add_argument("--out", type=Path, default=ROOT / "runs/bench_v2/oracle_crosscheck.json")
    args = ap.parse_args()
    data = json.loads(args.cases.read_text())
    rows = []
    for case in data["cases"]:
        phases = [("before", case["hidden"], case["gold_before"])]
        if case.get("correction"):
            c = case["correction"]
            phases.append(("after", {**case["hidden"], c["key"]: c["new"]}, case["gold_after"]))
        for phase, facts, gold in phases:
            a = analyse_many(case["claims_gold"], {k: v for k, v in facts.items() if v is not None}, data["today"])
            checks = score_assertions(a.to_dict(), gold)
            rows.append({"case_id": case["id"], "phase": phase, "checks": checks,
                         "disagreements": [r for r in checks if r["ok"] is False]})
    result = {"role": "diagnostic_crosscheck_only", "phases": len(rows),
              "disagreement_phases": sum(bool(r["disagreements"]) for r in rows), "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main()

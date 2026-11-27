#!/usr/bin/env python3
"""Isolated fault injections: detection, target removal, and ALL-defects-cleared repair."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lexflow.agent import ConsultationAgent
from lexflow.corpus import StatuteCorpus
from lexflow.elements import ElementSchema
from lexflow.llm import NullLLM
from lexflow.memory import CaseState, MemoryStore
from lexflow.rules import analyse_many
from lexflow.verify import Verifier

CODES = ["UNKNOWN_SOURCE", "VERSION_NOT_IN_FORCE", "QUOTE_MISMATCH", "SUPERSEDED_FACT", "UNVERIFIED_NUMBER"]


def inject(code, analysis, state):
    if code == "UNKNOWN_SOURCE":
        analysis.findings[0].cites = ["labor_contract@2008-01-01:第999条"]
    elif code == "VERSION_NOT_IN_FORCE":
        finding = next(f for f in analysis.findings if f.cites)
        finding.cites = ["tort_interp_2022@2022-05-01:第12条"]
        analysis.as_of = "2019-06-01"
    elif code == "QUOTE_MISMATCH":
        next(f for f in analysis.findings if f.cites).quote = "这是一段原文中不存在的引文"
    elif code == "SUPERSEDED_FACT":
        state.set_fact("monthly_wage", state.value("monthly_wage") + 100, turn=99)
    elif code == "UNVERIFIED_NUMBER":
        next(f for f in analysis.findings if f.id == "F_COMPENSATION").conclusion = "补偿约为 999,999 元。"
    else:
        raise ValueError(code)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "runs/bench_v2/verifier_repair.json")
    args = ap.parse_args()
    data = json.loads((ROOT / "data/eval/labor_cases_v2.json").read_text())
    corpus, schema = StatuteCorpus(), ElementSchema()
    verifier = Verifier(corpus)
    store = MemoryStore(":memory:")
    agent = ConsultationAgent(corpus, schema, store, llm=NullLLM(), today=data["today"])
    rows, clean = [], []
    try:
        for case in data["cases"]:
            if case["id"] not in ("B01", "B02", "B37", "B38"):
                continue
            state = CaseState(case["id"], case_type="labor_dismissal", matter="labor", claims=case["claims_gold"])
            for key, value in case["hidden"].items():
                state.set_fact(key, value)
            analysis = analyse_many(case["claims_gold"], case["hidden"], data["today"], state.revision)
            base = verifier.verify(analysis, state)
            clean.append({"case_id": case["id"], "defects": base["defects"]})
            baseline_state = copy.deepcopy(state.to_dict())
            for code in CODES:
                # Both world state and analysis are fresh; mutations cannot contaminate the next probe.
                a, s = copy.deepcopy(analysis), copy.deepcopy(state)
                inject(code, a, s)
                before = verifier.verify(a, s)
                actions = agent._repair(a, before, s)
                after = verifier.verify(a, s)
                rows.append({"case_id": case["id"], "code": code,
                             "detected": any(d["code"] == code for d in before["defects"]),
                             "target_removed": not any(d["code"] == code for d in after["defects"]),
                             "all_defects_cleared": not after["defects"],
                             "before": before, "after": after, "repair_actions": actions})
            if baseline_state != state.to_dict():
                raise AssertionError("fault injection mutated the shared baseline")
    finally:
        store.close()
    summary = {}
    for code in CODES:
        rs = [r for r in rows if r["code"] == code]
        summary[code] = {"n": len(rs), "detected": sum(r["detected"] for r in rs),
                         "target_removed": sum(r["target_removed"] for r in rs),
                         "all_defects_cleared": sum(r["all_defects_cleared"] for r in rs)}
    result = {"summary": summary, "clean": clean, "runs": rows,
              "note": "移除错误引用后若变成无引用，不能算修复成功；本实验只检查机械缺陷。"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": summary, "clean_defects": sum(len(x['defects']) for x in clean)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

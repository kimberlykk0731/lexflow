#!/usr/bin/env python3
"""Probe the verifier with injected defects.

A guardrail is only meaningful if it fires on errors.  For every scripted case
we take a clean analysis, inject one defect of each type, and check that the
verifier reports the expected code.  We also count false positives on clean
analyses.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from lexflow.agent import ConsultationAgent  # noqa: E402
from lexflow.corpus import StatuteCorpus  # noqa: E402
from lexflow.elements import ElementSchema  # noqa: E402
from lexflow.llm import build_llm  # noqa: E402
from lexflow.memory import MemoryStore  # noqa: E402
from lexflow.verify import Verifier  # noqa: E402
from protocol import ScriptedClient, load_cases  # noqa: E402


def clean_analysis(case, corpus, schema, today):
    agent = ConsultationAgent(corpus, schema, MemoryStore(":memory:"),
                              llm=build_llm(), today=today)
    client = ScriptedClient(case)
    r = agent.handle(case["id"], case["opening"], case_type=case["case_type"])
    n = 0
    while r.status == "asked" and n < 14:
        r = agent.handle(case["id"], client.answer(r.questions))
        n += 1
    if r.status != "answered":
        r = agent.handle(case["id"], "请出备忘录", force_memo=True)
    return agent, r


def main() -> None:
    data = load_cases()
    today = data.get("today", "2026-11-18")
    corpus = StatuteCorpus()
    schema = ElementSchema()
    verifier = Verifier(corpus)
    results = {"UNKNOWN_SOURCE": [], "VERSION_NOT_IN_FORCE": [],
               "QUOTE_MISMATCH": [], "SUPERSEDED_FACT": [],
               "UNVERIFIED_NUMBER": [], "clean_false_positive": []}

    for case in data["cases"]:
        agent, run = clean_analysis(case, corpus, schema, today)
        state = agent.store.load(run.session)
        analysis = agent._analysis_from_dict(run.analysis)
        base = verifier.verify(analysis, state)

        def check(code, mutate):
            a = copy.deepcopy(analysis)
            if not a.findings:
                return
            if mutate(a) is False:
                return
            res = verifier.verify(a, state)
            results[code].append({
                "case": case["id"],
                "detected": code in [d["code"] for d in res["defects"]],
            })

        def unknown_source(a):
            a.findings[0].cites = ["labor_contract@2008-01-01:第999条"]

        def bad_version(a):
            f = next((f for f in a.findings if f.cites), a.findings[0])
            f.cites = ["tort_interp_2022@2022-05-01:第12条"]
            a.as_of = "2019-06-01"

        def bad_quote(a):
            f = next((f for f in a.findings if f.cites), a.findings[0])
            f.quote = "这是一段原文中不存在的引文"

        def stale_fact(a):
            if not state.facts:
                return
            key = next(iter(state.facts))
            state.facts[key].revision = max(f.revision for f in state.facts.values()) + 5
            a.metadata["state_revision"] = 0

        def bad_number(a):
            f = next((f for f in a.findings if f.id == "F_COMPENSATION"), None)
            if not f:
                return False
            f.conclusion = "违法解除赔偿金约为 999,999 元。"

        check("UNKNOWN_SOURCE", unknown_source)
        check("VERSION_NOT_IN_FORCE", bad_version)
        check("QUOTE_MISMATCH", bad_quote)
        check("SUPERSEDED_FACT", stale_fact)
        check("UNVERIFIED_NUMBER", bad_number)
        results["clean_false_positive"].append({
            "case": case["id"], "count": len(base["defects"]),
        })

    summary = {}
    for code, rows in results.items():
        if code == "clean_false_positive":
            continue
        summary[code] = {
            "n": len(rows),
            "detected": sum(1 for r in rows if r["detected"]),
            "rate": round(sum(1 for r in rows if r["detected"]) / len(rows), 3) if rows else None,
        }
    fp = sum(r["count"] for r in results["clean_false_positive"])
    summary["clean_false_positive"] = {"n": len(results["clean_false_positive"]), "defects": fp}

    out = ROOT / "runs" / "verify_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "detail": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

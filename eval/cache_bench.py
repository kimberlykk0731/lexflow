#!/usr/bin/env python3
"""Two small cache experiments.

1. Warm replay: repeat a turn with no new facts.  A correct dependency-aware
   cache should execute zero tools; the no-cache baseline executes all of them.
2. Revision invalidation: correct a fact and check that dependent cache entries
   are dropped and the analysis is recomputed.
"""
from __future__ import annotations

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
from protocol import ScriptedClient, load_cases  # noqa: E402


def run_to_memo(agent, case, session):
    client = ScriptedClient(case)
    r = agent.handle(session, case["opening"], case_type=case["case_type"])
    n = 0
    while r.status == "asked" and n < 14:
        r = agent.handle(session, client.answer(r.questions))
        n += 1
    if r.status != "answered":
        r = agent.handle(session, "请出备忘录", force_memo=True)
    return r


def main() -> None:
    data = load_cases()
    case = next(c for c in data["cases"] if c["id"] == "L01")
    today = data.get("today", "2026-11-18")
    corpus = StatuteCorpus()
    schema = ElementSchema()
    out = {}

    for label, use_cache in (("cache_on", True), ("cache_off", False)):
        agent = ConsultationAgent(corpus, schema, MemoryStore(":memory:", cache=use_cache),
                                  llm=build_llm(), today=today)
        session = f"cache-{label}"
        run_to_memo(agent, case, session)
        warm = agent.handle(session, "请再复核一遍，事实没有变化。")
        out[label] = {"warm_executed": warm.tools.get("executed", 0),
                      "warm_cached": warm.tools.get("cached", 0)}

    # Revision invalidation
    agent = ConsultationAgent(corpus, schema, MemoryStore(":memory:"),
                              llm=build_llm(), today=today)
    session = "cache-revision"
    run_to_memo(agent, case, session)
    before = agent.store.cache_stats()["entries"]
    r = agent.handle(session, "更正：解除日期是2026年4月1日，不是3月15日。")
    after = agent.store.cache_stats()["entries"]
    out["revision"] = {
        "cache_entries_before": before,
        "invalidated": r.invalidated_cache,
        "cache_entries_after": after,
        "tools_executed": r.tools.get("executed", 0),
        "tools_cached": r.tools.get("cached", 0),
        "revision": r.revision,
    }

    path = ROOT / "runs" / "cache_bench.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

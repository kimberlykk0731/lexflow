#!/usr/bin/env python3
"""Create case cards and seven pending human reviews; optional separate-model audit."""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lexflow.config import LLMConfig
from lexflow.llm import build_llm, extract_json
from api_audit import AuditedLLM


def sample_cases(cases, n=7, seed=20261127):
    if n > len(cases) or n < 1:
        raise ValueError("sample size must be between one and dataset size")
    rng = random.Random(seed)
    chosen = []
    # Two mixed claims, two corrections, two unavailable facts, then random.
    for tag in ("multi_claim", "multi_claim", "correction", "correction", "unavailable_fact", "unavailable_fact"):
        candidates = [c for c in cases if tag in c["tags"] and c not in chosen]
        if candidates and len(chosen) < n:
            chosen.append(rng.choice(candidates))
    rest = [c for c in cases if c not in chosen]
    rng.shuffle(rest)
    return chosen + rest[:n - len(chosen)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=ROOT / "data/eval/labor_cases_v2.json")
    ap.add_argument("--out", type=Path, default=ROOT / "runs/bench_v2/review")
    ap.add_argument("--sample", type=int, default=7)
    ap.add_argument("--seed", type=int, default=20261127)
    ap.add_argument("--llm", choices=["offline", "api"], default="offline")
    ap.add_argument("--review-model", help="required for API auditing; choose independently of the generator")
    args = ap.parse_args()
    data = json.loads(args.cases.read_text())
    model = None
    if args.llm == "api":
        if not args.review_model:
            ap.error("--review-model required; review is not a legal certification")
        if args.review_model == data.get("generator_model"):
            ap.error("reviewer must differ from the surface generator model")
        try:
            model = AuditedLLM(build_llm(LLMConfig(mode="api", model=args.review_model), strict=True))
        except ValueError as exc:
            ap.error(str(exc))
    args.out.mkdir(parents=True, exist_ok=True)
    selected = sample_cases(data["cases"], args.sample, args.seed)
    csv_path = args.out / "human_review_sample.csv"
    if csv_path.exists():
        ap.error("review sample exists; choose a fresh --out to preserve human decisions")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "claim", "tags", "plausible", "facts_consistent",
                                              "assumptions_clear", "gold_supported", "decision", "notes", "reviewer"])
        writer.writeheader()
        for c in selected:
            writer.writerow({"case_id": c["id"], "claim": c["primary_claim"], "tags": ";".join(c["tags"]), "decision": "pending"})
    cards = ["# Bench v2 案例卡", "", "所有案例为合成；人工法律审定尚未完成。下列 gold 不可直接称为法律正确答案。", ""]
    audits = []
    for c in data["cases"]:
        cards += [f"## {c['id']} · {c['primary_claim']} · {c['split']}", "", c["opening"], "",
                  "```json", json.dumps({k: c[k] for k in ("claims_gold", "hidden", "critical", "gold_before", "gold_after", "assumptions")},
                                        ensure_ascii=False, indent=2), "```", "",
                  "更正：" + json.dumps(c.get("correction"), ensure_ascii=False), "",
                  "依据：" + "；".join(c["sources"]), ""]
        if model:
            result = model.complete([
                {"role": "system", "content": "你是独立评测审题人。检查合成案情、隐藏事实、假设和gold是否自洽。不要修改答案。仅输出JSON：{\"plausible\":bool,\"contradictions\":[],\"gold_concerns\":[],\"needs_human_review\":bool}。法律依据不充分必须指出。"},
                {"role": "user", "content": json.dumps(c, ensure_ascii=False)},
            ], temperature=0, max_tokens=1000)
            audits.append({"case_id": c["id"], "api_ok": result.ok,
                           "review": extract_json(result.text) if result.ok else None, "error": result.error})
    (args.out / "case_cards.md").write_text("\n".join(cards), encoding="utf-8")
    status = {"human_status": "pending", "sample_ids": [c["id"] for c in selected],
              "sample_ratio": len(selected) / len(data["cases"]),
              "model_status": "run" if model else "not_run", "audits": audits,
              "usage": model.summary() if model else None,
              "notice": "自动检查和模型审题不替代人工法律审定；不自动批准或覆盖gold。"}
    (args.out / "review_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in status.items() if k != "audits"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the controlled ablation and write a report.

Usage:
    PYTHONPATH=src python3 eval/run_evals.py
    PYTHONPATH=src python3 eval/run_evals.py --conditions full,gate_only
    PYTHONPATH=src python3 eval/run_evals.py --llm api          # needs LLM_API_KEY
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from lexflow.config import LLMConfig  # noqa: E402
from lexflow.corpus import StatuteCorpus  # noqa: E402
from lexflow.elements import ElementSchema  # noqa: E402
from lexflow.llm import build_llm  # noqa: E402
from protocol import CONDITIONS, aggregate, load_cases, run_case  # noqa: E402

COLUMNS = [
    ("coverage", "事实覆盖率", "{:.2%}"),
    ("inquiry_recall", "关键事实追问召回", "{:.2%}"),
    ("questions", "平均提问数", "{:.1f}"),
    ("premature_rate", "过早下结论率", "{:.2%}"),
    ("citation_support", "引用可核验率", "{:.2%}"),
    ("illegal_acc", "违法认定一致率", "{:.2%}"),
    ("amount_acc", "金额一致率", "{:.2%}"),
    ("limitation_acc", "时效一致率", "{:.2%}"),
    ("version_acc", "版本选择一致率", "{:.2%}"),
    ("stale_rate", "更正后仍用旧结论率", "{:.2%}"),
    ("latency_ms", "平均延迟(ms)", "{:.0f}"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--llm", default="mock", choices=["mock", "api"])
    ap.add_argument("--out", default=str(ROOT / "runs"))
    args = ap.parse_args()

    data = load_cases()
    cases = data["cases"][: args.limit] if args.limit else data["cases"]
    today = data.get("today", "2026-11-18")
    corpus = StatuteCorpus()
    schema = ElementSchema()
    cfg = LLMConfig()
    if args.llm == "api":
        cfg.mode = "api"
    llm = build_llm(cfg)

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = [c for c in conditions if c not in CONDITIONS]
    if unknown:
        raise SystemExit(f"unknown conditions: {unknown}; choose from {list(CONDITIONS)}")

    runs = []
    for condition in conditions:
        for case in cases:
            run = run_case(case, condition, corpus, schema, llm, today)
            runs.append(run)
            print(f"  {condition:18s} {case['id']:4s} status={run.status:8s} "
                  f"cov={run.coverage:.2f} lim={'Y' if run.limitation_ok else 'n'} "
                  f"amt={'Y' if run.amount_ok else ('n' if run.amount_ok is False else '-')} "
                  f"stale={run.stale_after_correction}")

    agg = aggregate(runs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval_results.json").write_text(json.dumps({
        "llm_mode": args.llm, "today": today, "n_cases": len(cases),
        "aggregate": agg, "runs": [r.to_dict() for r in runs],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with (out / "eval_cases.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "case_id", "condition", "status", "coverage", "inquiry_recall",
            "questions", "premature", "support_rate", "illegal_ok", "amount_ok",
            "limitation_ok", "version_ok", "stale_after_correction"])
        writer.writeheader()
        for r in runs:
            writer.writerow({k: getattr(r, k) for k in writer.fieldnames})

    lines = ["# 受控消融结果", "",
             f"- 案例数：{len(cases)}；模型模式：`{args.llm}`；评测基准日：{today}",
             "- 客户端为脚本化当事人：只回答被问到的问题，其余回答“不清楚”。",
             "- 指标仅描述本套脚本与当前规则层行为，不构成法律正确性结论。", "",
             "| 条件 | 事实覆盖率 | 追问召回 | 提问数 | 过早结论率 | 引用可核验率 | 违法认定 | 金额 | 时效 | 版本 | 旧结论残留 | 估算成本 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for cond, m in agg.items():
        def fmt(key):
            v = m.get(key)
            if v is None:
                return "—"
            for k, _, f in COLUMNS:
                if k == key:
                    return f.format(v)
            return str(v)
        lines.append(f"| {cond} | {fmt('coverage')} | {fmt('inquiry_recall')} | {fmt('questions')} | "
                     f"{fmt('premature_rate')} | {fmt('citation_support')} | {fmt('illegal_acc')} | "
                     f"{fmt('amount_acc')} | {fmt('limitation_acc')} | {fmt('version_acc')} | "
                     f"{fmt('stale_rate')} | {m.get('cost_rmb', 0):.4f} 元 |")
    lines += ["", "## 说明", "",
              "- **事实覆盖率**：备忘录生成时，金标准关键事实中已取得的比例。",
              "- **追问召回**：金标准关键事实中，系统主动问到的比例（与覆盖率不同：有些事实是当事人主动说的）。",
              "- **过早结论率**：关键事实未齐备就生成备忘录的比例。",
              "- **引用可核验率**：结论引用的法条存在、在案发日有效、引文可对上、所依赖事实未过期的比例。",
              "- **旧结论残留**：更正事实后，最终备忘录仍出现旧值的比例（仅含更正的案例）。",
              "- `full_no_revision` 刻意复用更正前的分析结果，用来模拟“事实改了但结论没跟着改”的常见缺陷。",
              "- 成本按 DeepSeek 2026 官方价估算：输入 1 元/百万 tokens、输出 2 元/百万 tokens（缓存未命中）；实际以账单为准。"]
    (out / "eval_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()

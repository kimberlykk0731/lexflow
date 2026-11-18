#!/usr/bin/env python3
"""Collect the generated artifacts into one report page.

Prefers the real-API run in runs/api/, and shows the mock run as an appendix.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lexflow.config import corpus_version  # noqa: E402
from lexflow.corpus import StatuteCorpus  # noqa: E402

RUNS = ROOT / "runs"


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def eval_table(ev: dict, include_cost: bool = True) -> list[str]:
    cols = ["条件", "覆盖率", "追问召回", "提问数", "过早结论", "引用核验",
            "违法", "金额", "时效", "版本", "旧结论残留"]
    if include_cost:
        cols.append("估算成本")
    lines = ["| " + " | ".join(cols) + " |",
             "|---|" + "---:|" * (len(cols) - 1)]
    for cond, m in ev["aggregate"].items():
        def pct(k):
            v = m.get(k)
            return "—" if v is None else f"{v:.1%}"
        row = [cond, pct("coverage"), pct("inquiry_recall"),
               f"{m.get('questions', 0):.1f}", pct("premature_rate"),
               pct("citation_support"), pct("illegal_acc"), pct("amount_acc"),
               pct("limitation_acc"), pct("version_acc"), pct("stale_rate")]
        if include_cost:
            row.append(f"{m.get('cost_rmb', 0):.4f} 元")
        lines.append("| " + " | ".join(row) + " |")
    return lines


def main() -> None:
    corpus = StatuteCorpus()
    api = load(RUNS / "api" / "eval_results.json")
    mock = load(RUNS / "mock" / "eval_results.json")
    probe = load(RUNS / "verify_probe.json")
    cache = load(RUNS / "cache_bench.json")
    main_ev = api or mock
    mode = main_ev["llm_mode"] if main_ev else "n/a"

    lines = ["# LexFlow 运行汇总", "",
             f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
             f"- 语料版本：`{corpus_version()}`（{len(corpus.articles)} 条法条，"
             f"{len({a.law_id for a in corpus.articles})} 部法规/解释）",
             f"- 主结果：`{mode}` 模式；mock 结果放在附录，仅作工程对照。", ""]

    if main_ev:
        total_cost = sum(m.get("cost_rmb", 0) for m in main_ev["aggregate"].values())
        total_prompt = sum(m.get("prompt_tokens", 0) for m in main_ev["aggregate"].values())
        total_completion = sum(m.get("completion_tokens", 0) for m in main_ev["aggregate"].values())
        lines += ["## 1. 受控消融（主结果）", "",
                  f"案例数 {main_ev['n_cases']}，模型模式 `{main_ev['llm_mode']}`，"
                  f"基准日 {main_ev['today']}。",
                  f"总消耗：{total_prompt:,} 输入 tokens + {total_completion:,} 输出 tokens，"
                  f"**估算 {total_cost:.3f} 元**。", ""]
        lines += eval_table(main_ev)
        lines += ["", "逐案例见 [`eval_cases.csv`](api/eval_cases.csv)。",
                  "成本按 DeepSeek 2026 官方价估算（输入 1 元/百万、输出 2 元/百万，缓存未命中）；"
                  "实际账单可能因缓存命中更低。", ""]

    if probe:
        lines += ["## 2. 核验器注入测试", "",
                  "| 缺陷类型 | 注入次数 | 检出 | 检出率 |", "|---|---:|---:|---:|"]
        for code, m in probe["summary"].items():
            if code == "clean_false_positive":
                continue
            lines.append(f"| `{code}` | {m['n']} | {m['detected']} | {m['rate']:.0%} |")
        fp = probe["summary"]["clean_false_positive"]
        lines += ["", f"干净分析误报：{fp['defects']} 条 / {fp['n']} 个案例。", ""]

    if cache:
        lines += ["## 3. 缓存实验", "",
                  "| 场景 | 执行工具 | 缓存命中 |", "|---|---:|---:|",
                  f"| 开缓存，无新事实重放 | {cache['cache_on']['warm_executed']} | {cache['cache_on']['warm_cached']} |",
                  f"| 关缓存，同样重放 | {cache['cache_off']['warm_executed']} | {cache['cache_off']['warm_cached']} |",
                  "", f"更正一个事实后：失效 {cache['revision']['invalidated']} 条缓存，"
                  f"重算执行 {cache['revision']['tools_executed']} 次工具，"
                  f"其余 {cache['revision']['tools_cached']} 次继续命中。", ""]

    if mock and api:
        lines += ["## 4. 附录：mock 模式（仅验证管线）", ""]
        lines += eval_table(mock, include_cost=False)
        lines += ["", "mock 模式不调用模型，成本为 0；它的作用是保证没有 API 时也能跑通全链路。", ""]

    lines += ["## 5. 复现命令", "", "```bash",
              "PYTHONPATH=src python3 -m unittest discover -s tests -v",
              "PYTHONPATH=src python3 eval/run_evals.py --llm api --out runs/api",
              "PYTHONPATH=src python3 eval/verify_probe.py",
              "PYTHONPATH=src python3 eval/cache_bench.py",
              "PYTHONPATH=src python3 eval/make_report.py",
              "PYTHONPATH=src python3 -m lexflow.cli demo --with-tort",
              "```", "",
              "## 6. 读表注意事项", "",
              "- 违法/金额/时效/版本的 100% 是规则层与金标准同源的结果，只能说明管线一致。",
              "- 主要信息量在：追问前后的覆盖率与过早结论率、修订前后的旧结论残留、注入测试的检出率。",
              "- 样本 12 个，描述性统计，不声称显著。"]
    (RUNS / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

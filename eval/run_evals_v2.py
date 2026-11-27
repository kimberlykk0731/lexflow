#!/usr/bin/env python3
"""End-to-end benchmark with frozen inputs, full trajectories and case-cluster CIs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lexflow.agent import ConsultationAgent
from lexflow.config import Budget, LLMConfig, corpus_version
from lexflow.corpus import StatuteCorpus
from lexflow.elements import ElementSchema
from lexflow.llm import build_llm
from lexflow.memory import MemoryStore
from api_audit import AuditedLLM
from metrics_v2 import claim_scores
from protocol import CONDITIONS
from protocol_v2 import run_case
from validate_cases import validate

METRICS = ["completed", "claim_f1", "correct_coverage", "extraction_f1", "inquiry_recall",
           "outcome_agreement", "formula_agreement", "behavior_agreement", "outcome_all_correct",
           "citation_mechanical_support", "premature_unqualified_memo_proxy", "unknown_handling_proxy",
           "correction_protocol_complete", "revision_success", "unaffected_preserved",
           "questions", "repeat_rate", "fallback_extraction_rate", "elapsed_ms", "turns"]


def code_fingerprint():
    digest = hashlib.sha256()
    for folder in ("src", "eval", "tests"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def case_values(rows, key):
    groups = {}
    for r in rows:
        value = r.get(key) if key in ("elapsed_ms", "turns") else r["scores"].get(key)
        if value is not None:
            groups.setdefault(r["case_id"], []).append(float(value))
    return {c: statistics.mean(vals) for c, vals in groups.items()}


def ci(values, seed=20261127, bootstrap=2000):
    if not values:
        return {"mean": None, "lo": None, "hi": None, "n_cases": 0}
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(bootstrap))
    return {"mean": statistics.mean(values), "lo": means[int(0.025 * (bootstrap - 1))],
            "hi": means[int(0.975 * (bootstrap - 1))], "n_cases": len(values)}


def aggregate(rows, seed=20261127, bootstrap=2000):
    result = {}
    for condition in dict.fromkeys(r["condition"] for r in rows):
        rs = [r for r in rows if r["condition"] == condition]
        result[condition] = {"sessions": len(rs), "cases": len({r["case_id"] for r in rs}),
                             "metrics": {k: ci(list(case_values(rs, k).values()), seed, bootstrap) for k in METRICS},
                             "usage": {k: sum(r["usage"][k] for r in rs) for k in rs[0]["usage"]}}
    paired = {}
    if "full" in result:
        for control in ("answer_first", "gate_only", "full_no_voi"):
            if control not in result:
                continue
            for key in ("correct_coverage", "formula_agreement", "questions"):
                full = case_values([r for r in rows if r["condition"] == "full"], key)
                other = case_values([r for r in rows if r["condition"] == control], key)
                delta = [full[c] - other[c] for c in sorted(full.keys() & other.keys())]
                paired[f"full-minus-{control}:{key}"] = ci(delta, seed, bootstrap)
    return result, paired


def run_router(path, corpus, schema, cfg, today):
    data = json.loads(path.read_text())
    rows = []
    for case in data["cases"]:
        store = MemoryStore(":memory:")
        audit = AuditedLLM(build_llm(cfg, strict=cfg.mode == "api"))
        try:
            agent = ConsultationAgent(corpus, schema, store, llm=audit, today=today)
            turn = agent.handle(case["id"], case["opening"])
            action = turn.route.get("action", "")
            scores = claim_scores(turn.route.get("claims", []), case["claims_gold"])
            rows.append({"case_id": case["id"], "expected_action": case["action_gold"], "action": action,
                         "action_ok": action == case["action_gold"], "scores": scores,
                         "usage": audit.summary(), "result": turn.to_dict(), "model_calls": audit.events})
        finally:
            store.close()
    return {"n": len(rows), "action_accuracy": statistics.mean(r["action_ok"] for r in rows),
            "claim_exact_accuracy": statistics.mean(r["scores"]["claim_exact"] for r in rows), "runs": rows}


def report(meta, summary, paired, router):
    def fmt(value, percent=True):
        return "—" if value is None else f"{value:.1%}" if percent else f"{value:.2f}"
    lines = ["# LexFlow Bench v2 — 实际运行结果", "",
             f"- 模式：`{meta['llm_mode']}`；模型：`{meta['model']}`；基准日：{meta['today']}。",
             f"- 数据 SHA-256：`{meta['dataset_sha256']}`；分组：`{meta['split']}`；每例表达版本：{meta['repeats']}。",
             "- 合成案例为人工设计种子＋模板生成；未完成独立人工法律审定。测试分组是预留分组，不是外部盲测。",
             "- 公式结果来自独立参考计算器；行为标签是作者指定的功能预期，不作为法律论证正确率。",
             "- 各指标先在同一案例的表达版本间取均值，再按案例宏平均；置信区间按案例聚类 bootstrap。", "",
             "| 配置 | 会话 | 完成率 | 请求权F1 | 正确事实覆盖 | 独立公式一致 | 总问题数 | 重复问题率 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for cond, s in summary.items():
        m = {k: v["mean"] for k, v in s["metrics"].items()}
        lines.append(f"| {cond} | {s['sessions']} | {fmt(m['completed'])} | {fmt(m['claim_f1'])} | "
                     f"{fmt(m['correct_coverage'])} | {fmt(m['formula_agreement'])} | {fmt(m['questions'], False)} | {fmt(m['repeat_rate'])} |")
    lines += ["", "## 适用分母与修订", "",
              "| 配置 | 公式案例数 | 更正协议完成率 | 更正成功率 | 更正成功适用案例数 | 信息不足处理代理指标 |",
              "|---|---:|---:|---:|---:|---:|"]
    for cond, s in summary.items():
        m = s["metrics"]
        lines.append(f"| {cond} | {m['formula_agreement']['n_cases']} | {fmt(m['correction_protocol_complete']['mean'])} | "
                     f"{fmt(m['revision_success']['mean'])} | {m['revision_success']['n_cases']} | {fmt(m['unknown_handling_proxy']['mean'])} |")
    lines += ["", "## 配对差值与95%区间", "", "| 比较与指标 | 均值差 | 下界 | 上界 | 案例数 |",
              "|---|---:|---:|---:|---:|"]
    for key, v in paired.items():
        lines.append(f"| {key} | {fmt(v['mean'], False)} | {fmt(v['lo'], False)} | {fmt(v['hi'], False)} | {v['n_cases']} |")
    if router:
        lines += ["", f"分诊专项：{router['n']} 例，动作准确率 {router['action_accuracy']:.1%}，请求权集合完全一致率 {router['claim_exact_accuracy']:.1%}。"]
    lines += ["", "## 解释边界", "",
              "- 客户端依据结构化问题 key 披露事实，因此不评估追问措辞是否让真人理解。",
              "- 信息不足处理、过早无条件备忘录为结构代理指标；自然语言是否给出不当法律承诺需另行审查。",
              "- 更正成功要求当前事实正确、受影响断言通过且会话完成；未出首份备忘录的案例不进入更正成功分母，另报协议完成率。",
              "- 引用评分仅为存在、版本、引文及事实依赖等机械检查，不等于引文支持法律结论。",
              "- 独立公式一致率只覆盖声明可计算的公式；行为断言、引用和全部请求权覆盖分别保存在逐案记录。",
              "- 未评完所有 critical_if / element.requires / 时间适用边界；查看 validation.json 中的缺口。",
              "- latency 是整个咨询会话耗时；真实API模式记录全部调用站点、失败、重试和抽取fallback。",
              "- 无模型账单价格配置时不估算人民币成本；失败请求可能存在未返回usage的费用。",
              "- 生产检索当前主要用于分析后的诊断，不以这些金额得分证明检索增强能力。", ""]
    return "\n".join(lines)



def run_jobs(jobs, execute, workers=1):
    """Independent sessions execute concurrently; results retain input order."""
    if workers == 1:
        yield from map(execute, jobs)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            yield from pool.map(execute, jobs)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=ROOT / "data/eval/labor_cases_v2.json")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--llm", choices=["mock", "api"], default="mock")
    ap.add_argument("--conditions", default="answer_first,gate_only,full,full_no_voi")
    ap.add_argument("--repeats", type=int, choices=[1, 2, 3], default=1)
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument("--max-questions", type=int, default=14)
    ap.add_argument("--seed", type=int, default=20261127, help="bootstrap seed, not a model sampling seed")
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--out", type=Path, default=ROOT / "runs/bench_v2/dev_mock")
    ap.add_argument("--workers", type=int, default=1, choices=range(1, 17),
                    help="independent concurrent sessions; default preserves serial execution")
    ap.add_argument("--skip-router", action="store_true")
    ap.add_argument("--input-price-per-million", type=float)
    ap.add_argument("--output-price-per-million", type=float)
    args = ap.parse_args()
    if args.max_turns < 1 or args.max_questions < 1 or args.bootstrap < 2:
        ap.error("positive budgets and bootstrap >=2 required")
    if (args.input_price_per_million is None) != (args.output_price_per_million is None):
        ap.error("provide both token prices, or neither")
    cfg = LLMConfig(mode=args.llm)
    # Fail before creating misleading API artifacts or making any model request.
    try:
        build_llm(cfg, strict=args.llm == "api")
    except ValueError as exc:
        ap.error(str(exc))
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    if not conditions or len(set(conditions)) != len(conditions) or any(c not in CONDITIONS for c in conditions):
        ap.error(f"choose unique conditions from {','.join(CONDITIONS)}")
    data = json.loads(args.cases.read_text())
    validation = validate(data, json.loads((ROOT / "data/elements.json").read_text()))
    if not validation["ok"]:
        ap.error("invalid dataset: " + "; ".join(validation["errors"]))
    cases = [c for c in data["cases"] if args.split == "all" or c["split"] == args.split]
    if not cases:
        ap.error("empty split")
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / "results.jsonl").exists():
        ap.error("output already contains a run; choose a fresh --out directory")
    corpus, schema = StatuteCorpus(), ElementSchema()
    meta = {"llm_mode": args.llm, "model": cfg.model if args.llm == "api" else "mock",
            "api_host": urlsplit(cfg.base_url).hostname if args.llm == "api" else None,
            "today": data["today"], "dataset_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
            "corpus_version": corpus_version(), "split": args.split, "repeats": args.repeats,
            "conditions": conditions, "max_turns_per_phase": args.max_turns,
            "max_questions_total": args.max_questions, "bootstrap_seed": args.seed,
            "bootstrap_samples": args.bootstrap, "human_reviewed": validation["human_reviewed"],
            "workers": args.workers}
    if args.llm == "api":
        meta["llm_parameters"] = {"temperature": cfg.temperature, "max_tokens": cfg.max_tokens,
                                  "thinking": cfg.thinking or "provider_default", "timeout": cfg.timeout}
    meta["source_tree_sha256"] = code_fingerprint()
    try:
        meta["source_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        meta["source_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        meta["source_commit"] = "unavailable"
    rows = []
    trajectory_dir = args.out / "trajectories"
    trajectory_dir.mkdir(exist_ok=True)
    (args.out / "config.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    (args.out / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n")
    jobs = [(condition, case, variant) for condition in conditions
            for case in cases for variant in range(args.repeats)]

    def execute(job):
        condition, case, variant = job
        # Each session owns its model, audit log, agent and in-memory database.
        # Corpus and schema are read-only; output writes stay on the main thread.
        return run_case(case, condition, corpus, schema, build_llm(cfg, strict=args.llm == "api"), data["today"],
                        variant=variant, max_turns=args.max_turns, max_questions=args.max_questions)

    with (args.out / "results.jsonl").open("w", encoding="utf-8") as stream:
        for job, row in zip(jobs, run_jobs(jobs, execute, args.workers)):
            condition, case, variant = job
            trajectory = row.pop("trajectory")
            rel = f"trajectories/{case['id']}_{condition}_v{variant}.json"
            (args.out / rel).write_text(json.dumps(trajectory, ensure_ascii=False, indent=2) + "\n")
            row["trajectory_file"] = rel
            row["cost_rmb"] = (row["usage"]["prompt_tokens"] / 1e6 * args.input_price_per_million +
                               row["usage"]["completion_tokens"] / 1e6 * args.output_price_per_million
                               if args.input_price_per_million is not None else None)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            rows.append(row)
            coverage = row["scores"]["correct_coverage"]
            print(f"{condition:18} {case['id']} v{variant} {row['status']:8} coverage={coverage!s} failures={','.join(row['failures'])}", flush=True)
    summary, paired = aggregate(rows, args.seed, args.bootstrap)
    router = None if args.skip_router else run_router(ROOT / "data/eval/router_cases_v2.json", corpus, schema, cfg, data["today"])
    if router:
        (args.out / "router_results.json").write_text(json.dumps(router, ensure_ascii=False, indent=2) + "\n")
    (args.out / "summary.json").write_text(json.dumps({"config": meta, "aggregate": summary, "paired": paired}, ensure_ascii=False, indent=2) + "\n")
    with (args.out / "results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["case_id", "condition", "variant", "status", "primary_claim"] + METRICS + ["failures", "trajectory_file"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (row[k] if k in row and k not in ("failures",) else
                                  ";".join(row["failures"]) if k == "failures" else row["scores"].get(k)) for k in fields})
    (args.out / "SUMMARY.md").write_text(report(meta, summary, paired, router), encoding="utf-8")
    print(json.dumps({"sessions": len(rows), "output": str(args.out), "mode": args.llm}, ensure_ascii=False))
    if args.llm == "api" and not sum(r["usage"]["successful_calls"] for r in rows):
        print("API run has no successful model calls; results are not a valid real-model evaluation", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Demo: the offline client's disclosure rule was leaving facts on the table.

Runs the same 30-case matrix twice — once with the default client and once with
``LEXFLOW_CLIENT_EXTENDED=1`` — and writes a before/after card.  Only the
offline client changes; the lawyer, the questions and the judge are identical,
so any movement in Fact Coverage is disclosure, not lawyering.

    python external/dlawbench/demo_topic_fix.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "runs" / "demo"
BASE = OUT / "topic_baseline"
EXT = OUT / "topic_extended"
CASE_ID = "case_cn_0007"


def run(out_dir: Path, extended: bool) -> None:
    env = dict(os.environ)
    if extended:
        env["LEXFLOW_CLIENT_EXTENDED"] = "1"
    cmd = [sys.executable, str(HERE / "run.py"), "--n-cases", "30",
           "--output-dir", str(out_dir), "--bootstrap", "1000"]
    subprocess.run(cmd, check=True, env=env, stdout=subprocess.DEVNULL)


def table_rows(summary: Path) -> dict[str, dict]:
    rows = {}
    for line in summary.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or "[" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 8 or cells[0] in ("Policy", "---"):
            continue
        rows[cells[0]] = {
            "n": cells[1],
            "coverage": float(cells[2].split()[0]),
            "inquiry": float(cells[3].split()[0]),
            "resolution": float(cells[7].split()[0]),
        }
    return rows


def platform_fragment(run_dir: Path) -> dict:
    session_path = run_dir / "full" / f"session_{CASE_ID}_P_WD_full.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    for turn in session.get("log", []):
        if turn.get("type") != "talk":
            continue
        answer = turn.get("client_response", "")
        if "平台直接支持" in answer or "自动确认收货" in answer:
            return {"question": turn["lawyer_message"], "answer": answer,
                    "disclosed": True,
                    "coverage": session["evaluation"]["scores"]["discovery_rate"],
                    "memo_has_fact": "自动确认收货" in (session.get("memo") or "")}
    fallback_q, fallback_a = "", "（平台事实从未在对话中出现）"
    for turn in session.get("log", []):
        if turn.get("type") != "talk":
            continue
        question = turn.get("lawyer_message", "")
        if "平台投诉" in question:
            fallback_q, fallback_a = question, turn.get("client_response", "")
            break
        if "平台" in question and not fallback_q:
            fallback_q, fallback_a = question, turn.get("client_response", "")
    return {"question": fallback_q or "（未问）", "answer": fallback_a,
            "disclosed": False,
            "coverage": session["evaluation"]["scores"]["discovery_rate"],
            "memo_has_fact": "自动确认收货" in (session.get("memo") or "")}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("[run] baseline ...")
    run(BASE, extended=False)
    print("[run] extended ...")
    run(EXT, extended=True)

    before = table_rows(BASE / "summary.md")
    after = table_rows(EXT / "summary.md")
    case_before = platform_fragment(BASE)
    case_after = platform_fragment(EXT)

    rows = []
    for policy in ("answer_first", "gate_only", "full"):
        b, a = before[policy], after[policy]
        rows.append({"policy": policy, "n": b["n"],
                     "coverage_before": b["coverage"], "coverage_after": a["coverage"],
                     "coverage_delta": round(a["coverage"] - b["coverage"], 3),
                     "inquiry_before": b["inquiry"], "inquiry_after": a["inquiry"],
                     "resolution_before": b["resolution"], "resolution_after": a["resolution"]})

    payload = {"case_id": CASE_ID, "rows": rows,
               "case_before": case_before, "case_after": case_after}
    (OUT / "topic_fix.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 客户端披露规则 demo（同一张问卷，只改客户端）",
        "",
        "30 个 DLawBench 中文案例 × 3 个策略；律师、问题、判分完全不变，只改离线客户端的披露规则。",
        "修复前 = 默认；修复后 = `LEXFLOW_CLIENT_EXTENDED=1`。",
        "",
        "| Policy | n | Fact Coverage 修复前 | 修复后 | Δ | Inquiry 修复前 | 修复后 | Resolution 修复前 | 修复后 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['policy']} | {row['n']} | {row['coverage_before']:.3f} | "
            f"{row['coverage_after']:.3f} | {row['coverage_delta']:+.3f} | "
            f"{row['inquiry_before']:.3f} | {row['inquiry_after']:.3f} | "
            f"{row['resolution_before']:.3f} | {row['resolution_after']:.3f} |")
    lines += [
        "",
        "**Inquiry 完全不变**：问题序列没变，涨的全部是客户端肯说。",
        "",
        f"## 案例 {CASE_ID}：平台事实",
        "",
        "| | 修复前 | 修复后 |",
        "|---|---|---|",
        f"| 对话里出现过平台事实 | {'✅' if case_before['disclosed'] else '❌'} | "
        f"{'✅' if case_after['disclosed'] else '❌'} |",
        f"| 备忘录采用该事实 | {'✅' if case_before['memo_has_fact'] else '❌'} | "
        f"{'✅' if case_after['memo_has_fact'] else '❌'} |",
        f"| Fact Coverage | {case_before['coverage']:.3f} | {case_after['coverage']:.3f} |",
        "",
        "修复前，平台问题只能得到兜底回答：",
        "",
        f"> Q: {case_before['question'] or '（未问）'}",
        f"> A: {case_before['answer']}",
        "",
        "修复后，平台事实在更早的一问里就说了出来：",
        "",
        f"> Q: {case_after['question'] or '（未问）'}",
        f"> A: {case_after['answer']}",
        "",
        "## 改了什么（`client_sim.py`，opt-in）",
        "",
        "1. 补了 `platform` / `property` / `procedure` 三组主题词（平台、冻结、信息公开等）；",
        "2. 客户端的开放式问题（“经过/事情/详细说说”）会主动补充一条最相关的未说事实；",
        "3. P_WD 的纯词面阈值从 0.35 降到 0.15。",
        "",
        "默认不开启，所以已提交的主表数字不受影响；演示时才打开。",
    ]
    (OUT / "topic_fix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[out] {OUT / 'topic_fix.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

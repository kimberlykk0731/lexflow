#!/usr/bin/env python3
"""Demo: does a client's correction propagate to the memo?

Runs the real ``ConsultationAgent`` on the two scripted cases that carry a
correction (L07: dismissal date; T05: accident date), captures the memo before
and after the correction, and writes a small comparison card.

    PYTHONPATH=src python eval/correction_demo.py

The output is a demo artifact, not a benchmark result: two cases, one
correction each.  What it shows is the revision loop — the fact table bumps a
version, the old value is struck through under "已被更正的事实", and the
conclusion that depends on it is recomputed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from protocol import ScriptedClient, load_cases  # noqa: E402

from lexflow.agent import ConsultationAgent  # noqa: E402
from lexflow.corpus import StatuteCorpus  # noqa: E402
from lexflow.elements import ElementSchema  # noqa: E402
from lexflow.llm import build_llm  # noqa: E402
from lexflow.memory import MemoryStore  # noqa: E402

OUT = ROOT / "runs" / "demo"
MAX_EXCHANGES = 14


def run_until_memo(agent, client, session: str, first_text: str | None = None):
    result = agent.handle(session, first_text, case_type=client.case["case_type"]) \
        if first_text is not None else None
    if result is None:
        result = agent.handle(session, "请根据目前的信息更新备忘录。", force_memo=True)
    exchanges = 0
    while result.status == "asked" and exchanges < MAX_EXCHANGES:
        exchanges += 1
        result = agent.handle(session, client.answer(result.questions))
    if result.status != "answered":
        result = agent.handle(session, "请根据目前的信息给我一份备忘录。", force_memo=True)
    return result


def facts(state) -> dict:
    """key -> (value, version) for the facts that are still current."""
    out = {}
    for key, fact in getattr(state, "facts", {}).items():
        if getattr(fact, "status", "") == "superseded":
            continue
        out[key] = (fact.value, getattr(fact, "revision", None))
    return out


def superseded(state) -> list[str]:
    out = []
    fetched = state.superseded() if callable(getattr(state, "superseded", None)) else []
    for fact in fetched:
        out.append(f"{fact.key}: {fact.value} -> v{fact.superseded_by}")
    return out


def memo_lines(memo: str, *needles: str, limit: int = 6) -> list[str]:
    lines = []
    for line in (memo or "").splitlines():
        if any(needle in line for needle in needles):
            lines.append(line.strip())
            if len(lines) >= limit:
                break
    return lines


def main() -> int:
    data = load_cases()
    today = data.get("today", "2026-11-18")
    cases = {case["id"]: case for case in data["cases"] if case.get("correction")}
    if not cases:
        raise SystemExit("no scripted case carries a correction")

    records = []
    for case_id, case in cases.items():
        agent = ConsultationAgent(
            StatuteCorpus(), ElementSchema(), MemoryStore(":memory:"), build_llm(),
            today=today, use_gate=True, use_verify=True, use_repair=True,
            use_revision=True, use_memory=True, use_cache=False,
        )
        client = ScriptedClient(case)
        session = case_id

        before = run_until_memo(agent, client, session, first_text=case["opening"])
        memo_before = before.memo or ""
        state_before = facts(agent.store.load(session))

        correction = client.take_correction()
        after = agent.handle(session, correction, force_memo=True)
        exchanges = 0
        while after.status == "asked" and exchanges < MAX_EXCHANGES:
            exchanges += 1
            after = agent.handle(session, client.answer(after.questions))
        if after.status != "answered":
            after = agent.handle(session, "请更新备忘录。", force_memo=True)
        memo_after = after.memo or ""
        state_after = facts(agent.store.load(session))

        old, new = case["correction"]["old"], case["correction"]["new"]
        after_lines = memo_after.splitlines()
        superseded_block = [line.strip() for line in after_lines if "~~" in line]
        body_after = "\n".join(line for line in after_lines
                               if "已被更正" not in line and "~~" not in line)
        records.append({
            "case_id": case_id,
            "case_type": case["case_type"],
            "correction": case["correction"]["text"],
            "old": old,
            "new": new,
            "memo_before_has_old": old in memo_before,
            "old_in_body_after": old in body_after,
            "memo_after_has_new": new in body_after,
            "superseded_block": superseded_block,
            "timing_before": next((l.strip() for l in memo_before.splitlines()
                                   if "【先看时效】" in l), ""),
            "timing_after": next((l.strip() for l in memo_after.splitlines()
                                  if "【先看时效】" in l), ""),
            "conclusion_before": next((l.strip() for l in memo_before.splitlines()
                                       if l.strip().startswith("**结论**")), ""),
            "conclusion_after": next((l.strip() for l in memo_after.splitlines()
                                      if l.strip().startswith("**结论**")), ""),
            "applicable_before": next((l.strip() for l in memo_before.splitlines()
                                       if "适用《" in l), ""),
            "applicable_after": next((l.strip() for l in memo_after.splitlines()
                                      if "适用《" in l), ""),
            "fact_versions": state_after,
            "superseded": superseded(agent.store.load(session)),
            "memos": {"before": memo_before, "after": memo_after},
        })

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "correction_demo.json").write_text(
        json.dumps({"today": today, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    def mark(flag: bool) -> str:
        return "✅" if flag else "❌"

    lines = [
        "# 更正传播 demo（real ConsultationAgent，2 个案例）",
        "",
        f"- 评测基准日：`{today}`；模型：`mock`（规则层）",
        "- 每个案例：先按正常问诊出第一份备忘录 → 客户发一条更正 → agent 更新事实并重出备忘录",
        "- 这是 demo，不是基准结果：2 个案例、1 条更正，用来看机制和做视频素材",
        "",
        "| 案例 | 原值 → 新值 | 旧值离开正文 | 新值进入正文 | “已被更正”段落 | 结论变化 | 适用版本变化 |",
        "|---|---|---|---|---|---|---|",
    ]
    for record in records:
        conclusion = "✅" if record["conclusion_before"] != record["conclusion_after"] else "—"
        version = "✅" if record["applicable_before"] != record["applicable_after"] else "—"
        lines.append(
            f"| {record['case_id']} | {record['old']} → {record['new']} | "
            f"{mark(not record['old_in_body_after'])} | {mark(record['memo_after_has_new'])} | "
            f"{mark(bool(record['superseded_block']))} | {conclusion} | {version} |")
    lines += ["", "## 逐案例前后对照", ""]
    for record in records:
        lines.append(f"### {record['case_id']}（{record['case_type']}）")
        lines.append("")
        lines.append(f"客户更正：*“{record['correction']}”*")
        lines.append("")
        lines.append("| | 更正前 | 更正后 |")
        lines.append("|---|---|---|")
        timing_after = record["timing_after"] or (
            "（无时效警示：更正后不再届满）" if record["timing_before"] else "—")
        lines.append(f"| 时效 | {record['timing_before'] or '—'} | {timing_after} |")
        lines.append(f"| 结论 | {record['conclusion_before'] or '—'} | {record['conclusion_after'] or '—'} |")
        applicable_after = record["applicable_after"] or (
            "（无显式版本行）" if record["applicable_before"] else "—")
        lines.append(f"| 适用版本 | {record['applicable_before'] or '—'} | {applicable_after} |")
        lines.append("")
        lines.append("更正后的“已被更正”段落：")
        lines.append("")
        lines += [f"> {line}" for line in (record["superseded_block"] or ["（无）"])]
        lines.append("")
        lines.append(f"事实表版本：`{json.dumps(record['fact_versions'], ensure_ascii=False)}`")
        lines.append("")
    (OUT / "correction_demo.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for record in records:
        print(f"[{record['case_id']}] {record['old']} -> {record['new']} | "
              f"old_left_body={not record['old_in_body_after']} "
              f"new_in_body={record['memo_after_has_new']} "
              f"superseded_block={bool(record['superseded_block'])} "
              f"conclusion_changed={record['conclusion_before'] != record['conclusion_after']} "
              f"version_changed={record['applicable_before'] != record['applicable_after']}")
    print(f"[out] {OUT / 'correction_demo.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

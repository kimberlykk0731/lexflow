"""Command line interface: scripted demo, interactive chat, memo inspection."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .agent import ConsultationAgent, TurnResult
from .config import Budget, LLMConfig, RUNS, corpus_version
from .corpus import StatuteCorpus
from .documents import (render_arbitration_application, render_demand_letter,
                        render_evidence_list, render_forced_resignation_notice,
                        render_legal_opinion)
from .elements import ElementSchema
from .guides import (arbitration_checklist, audit_contract,
                     compare_arbitration_litigation, deadline_card,
                     worker_rights_map)
from .llm import build_llm
from .memory import MemoryStore


LABOR_DEMO = [
    ("公司把我辞退了，理由是严重违纪，我想问能赔多少钱。", None),
    ("2026年3月15日通知的，员工手册从来没给我看过，也没有签收。", None),
    ("公司有员工手册，但制定的时候没经过民主程序，解除前也没通知工会。", None),
    ("我2021年5月入职的，月薪一万五，想要赔偿金。", None),
    ("违纪的事公司只有口头说，没有书面证据。合同签了但没给我，公司叫北京示例科技有限公司。", None),
    ("更正一下，我是2022年8月1日入职的，不是2021年5月。", None),
]

TORT_DEMO = [
    ("我父亲2022年3月1日出车祸去世了，对方主要责任，我们想起诉赔偿。", None),
    ("我们户籍是农村的，对方车辆有交强险和商业三者险。", None),
    ("更正一下：事故不是2022年3月，是2024年11月1日，我一直记错了。", None),
]


def make_agent(args) -> ConsultationAgent:
    corpus = StatuteCorpus()
    schema = ElementSchema()
    store = MemoryStore(args.db, cache=not args.no_cache, memory=not args.no_memory)
    cfg = LLMConfig()
    if args.llm == "api":
        cfg.mode = "api"
    llm = build_llm(cfg)
    if args.llm == "api" and not llm.enabled:
        print("⚠️  未检测到 LLM_API_KEY，回退到 mock 模式。"
              "设置 LLM_API_KEY/LLM_BASE_URL/LLM_MODEL 后可启用真实模型。")
    return ConsultationAgent(
        corpus, schema, store, llm=llm,
        budget=Budget(max_questions=args.max_questions),
        use_gate=not args.no_gate, use_verify=not args.no_verify,
        use_repair=not args.no_repair, use_revision=not args.no_revision,
        today=args.today,
    )


def _write_demo(steps: list[TurnResult], out: Path, title: str, meta: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    trace = {
        "title": title,
        "meta": meta,
        "turns": [
            {
                "turn": r.turn, "status": r.status, "reply": r.reply,
                "questions": r.questions, "changed": r.changed,
                "revision": r.revision, "invalidated_cache": r.invalidated_cache,
                "tools": r.tools, "verification": r.verification,
                "analysis": r.analysis, "memo": r.memo, "trace": r.trace,
            } for r in steps
        ],
    }
    (out / f"{title}_trace.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# {title} 演示记录", "",
             f"- 语料版本：{meta['corpus_version']}；模型：{meta['llm']}；会话：{meta['session']}",
             f"- 分析基准日：{meta['today']}；共 {len(steps)} 轮", "",
             "> 演示输出不构成正式法律意见。", ""]
    for r in steps:
        lines += [f"## 第 {r.turn} 轮（{r.status}）", "",
                  "**用户**：" + (r.trace[0].get("text", "") if r.trace else ""), ""]
        lines += ["**系统**：", "", r.reply, ""]
        if r.changed:
            lines += ["已更新事实：" + "、".join(r.changed) +
                      f"（案例版本 v{r.revision}，失效缓存 {r.invalidated_cache} 条）", ""]
        if r.status == "answered":
            lines += ["<details><summary>查看备忘录</summary>", "", r.memo, "</details>", ""]
    (out / f"{title}_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_scripted(agent: ConsultationAgent, dialogue, session: str) -> list[TurnResult]:
    steps = []
    for text, _ in dialogue:
        r = agent.handle(session, text)
        steps.append(r)
        print(f"\n=== 第 {r.turn} 轮 · {r.status} ===")
        print(r.reply)
        if r.status == "answered":
            print(f"\n[备忘录 {len(r.memo)} 字，引用核验 "
                  f"{r.verification.get('support_rate', 0):.0%}]")
    return steps


def demo(args) -> None:
    scenarios = [("labor_demo", LABOR_DEMO)]
    if args.with_tort:
        scenarios.append(("tort_demo", TORT_DEMO))
    print(f"LexFlow demo | 语料 {corpus_version()} | 今天 {args.today}")
    for name, dialogue in scenarios:
        agent = make_agent(args)
        session = f"{args.session}-{name}-{int(time.time())}"
        meta = {"corpus_version": corpus_version(), "llm": agent.llm.name,
                "session": session, "today": args.today}
        print(f"\n### 场景：{name} | LLM: {agent.llm.name}")
        steps = run_scripted(agent, dialogue, session)
        if steps and steps[-1].status != "answered":
            steps.append(agent.handle(session, "请根据目前信息生成备忘录。",
                                      force_memo=True))
            print("\n[已强制生成备忘录]")
        _write_demo(steps, Path(args.out), name, meta)
        print(f"\n完整备忘录已写入 {args.out}/{name}_report.md")


def _state_analysis(agent: ConsultationAgent, session: str):
    state = agent.store.load(session)
    if not state.last_analysis:
        return state, None
    return state, agent._analysis_from_dict(state.last_analysis)


def chat(args) -> None:
    agent = make_agent(args)
    session = args.session
    print(f"LexFlow 交互模式 | LLM: {agent.llm.name}")
    print("输入 /help 看命令；/memo 出备忘录；/letter 法律意见书；"
          "/compare 仲裁vs诉讼；/quit 退出")
    while True:
        try:
            text = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text in {"/quit", "/exit", "q"}:
            break
        if text == "/help":
            print("""
命令：
  /memo        生成备忘录
  /facts       查看已记录事实
  /claims      查看当前请求类型
  /letter      生成法律意见书
  /arbitration 生成劳动仲裁申请书
  /evidence    生成证据清单
  /demand      生成催告函/律师函草稿
  /resign      生成被迫解除通知书
  /compare     仲裁 vs 诉讼对比
  /checklist   劳动仲裁材料清单
  /deadlines   关键期限卡片
  /contract    劳动合同条款体检（把条款粘在命令后面）
  /rights      打工人权益地图
""")
            continue
        if text == "/facts":
            state = agent.store.load(session)
            for f in state.fact_table():
                label = agent.schema.field_any(f["key"])
                print(f"  {(label.label if label else f['key']):20s} "
                      f"{f['value']!s:20s} {f['status']:12s} v{f['revision']}")
            continue
        if text == "/claims":
            state = agent.store.load(session)
            print("当前请求：" + ("、".join(agent.schema.label(c) for c in state.claims)
                                or "（尚未识别）"))
            continue
        if text == "/rights":
            print(worker_rights_map())
            continue
        if text == "/deadlines":
            state = agent.store.load(session)
            print(deadline_card(state, agent.schema, args.today))
            continue
        if text.startswith("/contract"):
            clause = text[len("/contract"):].strip()
            if not clause:
                clause = input("把合同条款粘贴进来：").strip()
            print(audit_contract(clause))
            continue
        if text == "/compare":
            state = agent.store.load(session)
            print(compare_arbitration_litigation(state, agent.schema))
            continue
        if text == "/checklist":
            state = agent.store.load(session)
            print(arbitration_checklist(state, agent.schema))
            continue
        state, analysis = _state_analysis(agent, session)
        if text in ("/letter", "/arbitration", "/evidence", "/demand", "/resign"):
            if text != "/resign" and analysis is None:
                print("还没有可用的分析；请先描述情况，或输入 /memo。")
                continue
            if text == "/letter":
                print(render_legal_opinion(analysis, state, agent.schema))
            elif text == "/arbitration":
                print(render_arbitration_application(analysis, state, agent.schema))
            elif text == "/evidence":
                print(render_evidence_list(analysis, state, agent.schema))
            elif text == "/demand":
                print(render_demand_letter(analysis, state, agent.schema))
            else:
                print(render_forced_resignation_notice(state, agent.schema))
            continue
        if text == "/memo":
            r = agent.handle(session, "请根据目前信息生成备忘录。", force_memo=True)
        else:
            r = agent.handle(session, text)
        print("\n" + r.reply)
        if r.route.get("note"):
            print("\n（说明：" + r.route["note"] + "）")
        if r.status == "answered" and r.memo:
            print("\n" + "-" * 60)
            print(r.memo)


def main() -> None:
    ap = argparse.ArgumentParser(description="LexFlow legal consultation agent")
    ap.add_argument("command", nargs="?", default="demo", choices=["demo", "chat"])
    ap.add_argument("--db", default=str(RUNS / "lexflow.sqlite"))
    ap.add_argument("--out", default=str(RUNS))
    ap.add_argument("--session", default="demo-case")
    ap.add_argument("--llm", default="mock", choices=["mock", "api"])
    ap.add_argument("--today", default="2026-11-18")
    ap.add_argument("--max-questions", type=int, default=14)
    ap.add_argument("--with-tort", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--no-memory", action="store_true")
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--no-repair", action="store_true")
    ap.add_argument("--no-revision", action="store_true")
    args = ap.parse_args()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    if args.command == "demo":
        demo(args)
    else:
        chat(args)


if __name__ == "__main__":
    main()

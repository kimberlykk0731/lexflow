"""Streamlit demo UI for LexFlow.

Run from the project root:
    PYTHONPATH=src streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lexflow.agent import ConsultationAgent  # noqa: E402
from lexflow.cli import LABOR_DEMO  # noqa: E402
from lexflow.config import Budget, LLMConfig, RUNS, corpus_version  # noqa: E402
from lexflow.corpus import StatuteCorpus  # noqa: E402
from lexflow.documents import (render_arbitration_application, render_demand_letter,  # noqa: E402
                               render_evidence_list, render_forced_resignation_notice,
                               render_legal_opinion)
from lexflow.elements import ElementSchema  # noqa: E402
from lexflow.guides import (arbitration_checklist,  # noqa: E402
                            compare_arbitration_litigation, worker_rights_map)
from lexflow.llm import build_llm  # noqa: E402
from lexflow.memory import MemoryStore  # noqa: E402

st.set_page_config(page_title="LexFlow · 法律咨询 Agent", layout="wide")

# Streamlit Community Cloud passes secrets via st.secrets, not the shell env.
# Copy the four keys we understand into os.environ before LLMConfig is built.
try:
    for _key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LEXFLOW_LLM"):
        if _key not in os.environ and _key in st.secrets:
            os.environ[_key] = str(st.secrets[_key])
except Exception:
    pass
st.markdown(
    """
    <style>
    div[data-testid="stMarkdownContainer"] h1 { font-size: 1.55rem; }
    div[data-testid="stMarkdownContainer"] h2 { font-size: 1.2rem; margin-top: 1.1rem; }
    div[data-testid="stMarkdownContainer"] h3 { font-size: 1.02rem; }
    section[data-testid="stSidebar"] h1 { font-size: 1.8rem; }
    .block-container { padding-top: 2.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

STATUS = {"asked": "追问中", "answered": "已出备忘录", "error": "出错",
          "clarify": "需要补充问题类型", "out_of_scope": "超出当前覆盖范围"}
FACT_STATUS = {"user_stated": "当事人陈述", "documentary": "材料支持",
               "verified": "已核验", "unknown": "不清楚"}


@st.cache_resource
def load_knowledge():
    return StatuteCorpus(), ElementSchema()


def new_agent(session: str, today: str, use_gate: bool = True) -> ConsultationAgent:
    corpus, schema = load_knowledge()
    store = MemoryStore(RUNS / "ui.sqlite")
    cfg = LLMConfig()
    return ConsultationAgent(corpus, schema, store, llm=build_llm(cfg),
                             budget=Budget(max_questions=14), use_gate=use_gate,
                             today=today)


def init() -> None:
    if "session" not in st.session_state:
        st.session_state.session = f"ui-case-{int(time.time())}"
        st.session_state.today = "2026-11-18"
        st.session_state.history = []
        st.session_state.last = None
        st.session_state.agent = new_agent(st.session_state.session,
                                           st.session_state.today)


def reset() -> None:
    st.session_state.session = f"ui-case-{int(time.time())}"
    st.session_state.history = []
    st.session_state.last = None
    st.session_state.agent = new_agent(st.session_state.session, st.session_state.today)


def submit(text: str) -> None:
    agent = st.session_state.agent
    r = agent.handle(st.session_state.session, text)
    st.session_state.history.append({"role": "user", "content": text})
    st.session_state.history.append({"role": "assistant", "content": r.reply,
                                     "status": r.status})
    st.session_state.last = r


def main() -> None:
    init()
    corpus, schema = load_knowledge()

    if st.query_params.get("demo") == "1" and not st.session_state.get("demo_loaded"):
        st.session_state.demo_loaded = True
        reset()
        for text, _ in LABOR_DEMO:
            submit(text)
        st.rerun()

    with st.sidebar:
        st.title("LexFlow")
        st.caption("面向法律咨询的「先问再答」Agent · NLP 课程项目")
        st.write(f"语料版本：`{corpus_version()}`（{len(corpus.articles)} 条法条）")
        st.write(f"模型：`{st.session_state.agent.llm.name}`")
        st.write(f"分析基准日：`{st.session_state.today}`")
        _last0 = st.session_state.get("last")
        if _last0 is not None and _last0.claims:
            st.write("当前请求：" + "、".join(
                schema.label(c) for c in _last0.claims))
        st.divider()
        if st.button("新会话", use_container_width=True):
            reset()
            st.rerun()
        if st.button("载入示例对话", use_container_width=True):
            for text, _ in LABOR_DEMO:
                submit(text)
            st.rerun()
        if st.button("直接出备忘录", use_container_width=True):
            agent = st.session_state.agent
            r = agent.handle(st.session_state.session, "请根据目前信息生成备忘录。",
                             force_memo=True)
            st.session_state.history.append({"role": "user", "content": "（直接出备忘录）"})
            st.session_state.history.append({"role": "assistant", "content": r.reply,
                                             "status": r.status})
            st.session_state.last = r
            st.rerun()
        st.divider()
        last = st.session_state.last
        if last is not None:
            st.metric("事实版本", f"v{last.revision}")
            st.metric("已记录事实", len([f for f in last.facts if f["superseded_by"] is None]))
            if last.tools:
                st.caption(f"工具：执行 {last.tools.get('executed', 0)} / "
                           f"缓存命中 {last.tools.get('cached', 0)}")
            if last.status == "answered":
                st.caption(f"引用核验：{last.verification.get('support_rate', 0):.0%}")

    left, right = st.columns([1.15, 1], gap="large")

    with left:
        st.subheader("咨询对话")
        for msg in st.session_state.history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant" and msg.get("status"):
                    st.caption(STATUS.get(msg["status"], msg["status"]))
        text = st.chat_input("用大白话描述你的情况，例如：公司把我辞退了，理由是严重违纪……")
        if text:
            submit(text)
            st.rerun()

    with right:
        last = st.session_state.last
        options = ["事实状态", "要件链", "备忘录", "争点与引用", "文书", "运行轨迹"]
        default = "备忘录" if (last and last.memo) else "事实状态"
        choice = st.segmented_control("视图", options, default=default,
                                      label_visibility="collapsed")
        choice = choice or default
        if choice == "事实状态":
            if not last:
                st.info("还没有对话。可以先点左侧「载入示例对话」。")
            else:
                rows = []
                for f in last.facts:
                    if f["superseded_by"] is not None:
                        continue
                    _fld = schema.field_any(f["key"])
                    rows.append({"事实": _fld.label if _fld else f["key"],
                                 "内容": str(f["value"]),
                                 "状态": FACT_STATUS.get(f["status"], f["status"]),
                                 "版本": f"v{f['revision']}"})
                if rows:
                    st.table(rows)
                else:
                    st.info("还没有记录到事实。")
                old = [f for f in last.facts if f["superseded_by"] is not None]
                if old:
                    st.caption("已更正：" + "；".join(f"{f['key']} 旧值 {f['value']}" for f in old))
        elif choice == "要件链":
            if last and last.chain:
                for claim in last.chain:
                    st.markdown(f"### {schema.label(claim['claim'])}")
                    if claim.get("summary"):
                        st.caption(claim["summary"])
                    for el in claim.get("elements", []):
                        icon = {"satisfied": "✅", "partial": "⚠️",
                                "unknown": "○", "blocked": "—"}.get(el["status"], "○")
                        st.markdown(f"{icon} **{el['label']}**")
                        known = [f for f in el.get("facts", []) if f.get("known")]
                        open_ = [f for f in el.get("facts", []) if not f.get("known")]
                        if known:
                            st.caption("已具备：" + "；".join(
                                f"{f['label']}＝{f['value']}" for f in known))
                        if open_:
                            st.caption("待确认：" + "、".join(f["label"] for f in open_))
            else:
                st.info("还没有要件链。")
        elif choice == "备忘录":
            if last and last.memo:
                st.markdown(last.memo)
            else:
                st.info("关键事实齐备后（或点击「直接出备忘录」）才会生成备忘录。")
        elif choice == "争点与引用":
            if last and last.analysis:
                for f in last.analysis.get("findings", []):
                    st.markdown(f"**{f['issue']}** `风险：{f['risk']}`")
                    st.write(f["conclusion"])
                    if f.get("cites"):
                        st.caption("依据：" + "；".join(f["cites"]))
                    st.divider()
                if last.verification.get("defects"):
                    st.warning("核验问题：\n" + "\n".join(
                        f"- `{d['code']}` {d['detail']}" for d in last.verification["defects"]))
            else:
                st.info("暂无分析结果。")
        elif choice == "文书":
            if not last or not last.analysis:
                st.info("先完成一次分析，或点击「直接出备忘录」。")
            else:
                state = st.session_state.agent.store.load(st.session_state.session)
                analysis = st.session_state.agent._analysis_from_dict(last.analysis)
                kind = st.selectbox("文书类型", ["法律意见书", "劳动仲裁申请书", "证据清单",
                                                 "催告函", "被迫解除通知书",
                                                 "仲裁 vs 诉讼", "仲裁材料清单"])
                if kind == "法律意见书":
                    st.markdown(render_legal_opinion(analysis, state, schema,
                                                     last.verification))
                elif kind == "劳动仲裁申请书":
                    st.markdown(render_arbitration_application(analysis, state, schema))
                elif kind == "证据清单":
                    st.markdown(render_evidence_list(analysis, state, schema))
                elif kind == "催告函":
                    st.markdown(render_demand_letter(analysis, state, schema))
                elif kind == "被迫解除通知书":
                    st.markdown(render_forced_resignation_notice(state, schema))
                elif kind == "仲裁 vs 诉讼":
                    st.markdown(compare_arbitration_litigation(state, schema))
                else:
                    st.markdown(arbitration_checklist(state, schema))
                st.caption("以上均为草稿，需核对身份信息、金额和管辖后使用。")
        elif choice == "运行轨迹":
            if last:
                st.json(last.trace, expanded=False)


if __name__ == "__main__":
    main()

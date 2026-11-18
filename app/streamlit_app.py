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
from lexflow.elements import ElementSchema  # noqa: E402
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

STATUS = {"asked": "追问中", "answered": "已出备忘录", "error": "出错"}
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
        options = ["事实状态", "备忘录", "争点与引用", "运行轨迹"]
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
                    rows.append({"事实": f["key"], "内容": str(f["value"]),
                                 "状态": FACT_STATUS.get(f["status"], f["status"]),
                                 "版本": f"v{f['revision']}"})
                if rows:
                    st.table(rows)
                else:
                    st.info("还没有记录到事实。")
                old = [f for f in last.facts if f["superseded_by"] is not None]
                if old:
                    st.caption("已更正：" + "；".join(f"{f['key']} 旧值 {f['value']}" for f in old))
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
        elif choice == "运行轨迹":
            if last:
                st.json(last.trace, expanded=False)


if __name__ == "__main__":
    main()

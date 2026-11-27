"""Streamlit demo UI for LexFlow.

Run from the project root:
    PYTHONPATH=src streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import hashlib
import os
import sys
import time
from dataclasses import fields
from pathlib import Path
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lexflow.agent import ConsultationAgent, TurnResult  # noqa: E402
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
from lexflow.path import render_path_markdown  # noqa: E402
from lexflow.exports import export_docx, export_pdf, missing_fields, plain_text  # noqa: E402

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
    /* Keep the first row below Streamlit's fixed 60px toolbar. */
    .block-container { padding-top: calc(60px + 1rem); }
    </style>
    """,
    unsafe_allow_html=True,
)

STATUS = {"asked": "追问中", "answered": "已出备忘录", "error": "出错",
          "clarify": "需要补充问题类型", "out_of_scope": "超出当前覆盖范围",
          "explained": "前文解释"}
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
        requested = str(st.query_params.get("session", ""))
        store = MemoryStore(RUNS / "ui.sqlite")
        try:
            exists = bool(requested) and store.session_exists(requested)
        finally:
            store.close()
        activate_session(requested if exists else f"ui-case-{uuid4().hex}")


def activate_session(session: str) -> None:
    old_agent = st.session_state.get("agent")
    if old_agent is not None:
        old_agent.store.close()
    store = MemoryStore(RUNS / "ui.sqlite")
    try:
        today = store.session_date(session)
        history = [{"role": m["role"], "content": m["content"],
                    "status": m["meta"].get("status")}
                   for m in store.history(session)]
        snapshot = store.last_result(session)
        store.save_session(session, today)
    finally:
        store.close()
    st.session_state.session = session
    st.session_state.today = today
    st.session_state.history = history
    names = {f.name for f in fields(TurnResult)}
    st.session_state.last = (TurnResult(**{k: v for k, v in snapshot.items() if k in names})
                             if snapshot else None)
    st.session_state.agent = new_agent(session, today)
    st.session_state.request_error = ""
    st.query_params["session"] = session


def reset() -> None:
    activate_session(f"ui-case-{uuid4().hex}")


def submit(text: str, force_memo: bool = False, skip_keys: list[str] | None = None) -> None:
    agent = st.session_state.agent
    session = st.session_state.session
    agent.store.prepare_request(session, text, force_memo, skip_keys)
    st.session_state.request_error = ""
    with st.status("正在处理您的消息…", expanded=True) as status:
        try:
            r = agent.handle(session, text, force_memo=force_memo, skip_keys=skip_keys,
                             on_progress=lambda message: status.update(label=message))
        except Exception:
            # Do not print credentials, request bodies or private traceback data.
            st.session_state.request_error = "本次处理未完成。请重试本轮；此前的记录仍保留。"
            status.update(label="处理未完成，可以重试", state="error")
            return
        degraded = bool(r.metrics.get("api", {}).get("failures") or r.metrics.get("api", {}).get("fallbacks"))
        status.update(label="已完成（部分步骤使用规则兜底）" if degraded else "已完成",
                      state="complete", expanded=False)
    st.session_state.history = [{"role": m["role"], "content": m["content"],
                                 "status": m["meta"].get("status")}
                                for m in agent.store.history(session)]
    st.session_state.last = r


def retry_request() -> None:
    agent = st.session_state.agent
    try:
        request = agent.store.rewind_request(st.session_state.session)
    except ValueError:
        st.session_state.request_error = "这条消息之后已有新的对话，请直接发送需要补充的内容。"
        return
    agent.composer._cache.clear()
    submit(**request)


def document_editor(content: str, kind: str) -> None:
    store = st.session_state.agent.store
    session = st.session_state.session
    source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    saved = store.draft(session, kind)
    key = f"document:{session}:{kind}"
    if saved and saved["source_hash"] != source_hash:
        st.info("案情或分析已更新；保留了您上次编辑的草稿，请核对后使用。")
    if st.button("根据最新分析重新生成草稿", key=f"reset:{key}"):
        st.session_state[key] = content
        saved = None
    if key not in st.session_state:
        st.session_state[key] = saved["content"] if saved else content
    edited = st.text_area("编辑文书（修改后点击输入框外保存）", key=key, height=380)
    basis = saved["source_hash"] if saved else source_hash
    if not saved or saved["content"] != edited:
        store.save_draft(session, kind, edited, basis)
    missing = missing_fields(edited)
    if missing:
        with st.expander(f"还有 {len(missing)} 处信息待填写", expanded=True):
            for item in missing:
                st.write("• " + item)
    # Encode text as a JS string, escaping '<' to prevent script/HTML injection.
    copy_value = json.dumps(plain_text(edited), ensure_ascii=False).replace("<", "\\u003c")
    components.html('''<button id="copy" style="padding:9px 20px;border:1px solid #bbb;border-radius:7px;background:white;cursor:pointer">复制全文</button>
<script>const text = ''' + copy_value + ''';
document.getElementById('copy').onclick = async function(){
  try { await navigator.clipboard.writeText(text); this.textContent='已复制'; }
  catch(e){ const box=document.createElement('textarea'); box.value=text;
    document.body.appendChild(box); box.select(); const ok=document.execCommand('copy'); box.remove();
    this.textContent=ok?'已复制':'请使用下方文本框复制'; }
};</script>''', height=48)
    with st.expander("复制备用文本"):
        st.code(plain_text(edited), language=None)
    with st.expander("排版预览"):
        st.markdown(edited)
    try:
        word = export_docx(edited)
        pdf = export_pdf(edited)
    except ImportError:
        st.warning("文书导出组件未安装，请安装项目 requirements.txt 后重启。")
        return
    except Exception:
        st.error("文书排版失败，编辑内容已保存。请检查内容后重试。")
        return
    a, b = st.columns(2)
    a.download_button("下载 Word", word, file_name=f"{kind}.docx",
                      mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    b.download_button("下载 PDF", pdf, file_name=f"{kind}.pdf", mime="application/pdf")


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
        sessions = st.session_state.agent.store.list_sessions()
        if sessions:
            st.caption("历史咨询保存在本机，可恢复对话、事实和上次分析。")
            labels = {s["session"]: f"{s['title']} · {s['session'][-6:]}" for s in sessions}
            with st.form("history_picker"):
                selected = st.selectbox("历史会话", [None, *labels],
                                        format_func=lambda sid: labels.get(sid, "选择一段历史咨询"))
                restore = st.form_submit_button("恢复会话", use_container_width=True)
            if restore and selected:
                activate_session(selected)
                st.rerun()
        if st.button("载入示例对话", use_container_width=True):
            reset()
            for text, _ in LABOR_DEMO:
                submit(text)
            st.rerun()
        if st.button("直接出备忘录", use_container_width=True):
            submit("请根据目前信息生成备忘录。", force_memo=True)
            st.rerun()
        st.divider()
        last = st.session_state.last
        api = last.metrics.get("api", {}) if last else {}
        error = st.session_state.get("request_error", "")
        if error:
            st.error(error)
        if api.get("failures") or api.get("fallbacks"):
            st.warning("部分模型步骤未成功，已采用规则兜底；请核对结果或重试本轮。")
            for message in api.get("errors", []):
                st.caption(message)
        if error or api.get("failures") or api.get("fallbacks"):
            if st.button("重试本轮", use_container_width=True):
                retry_request()
                st.rerun()
        if api.get("calls"):
            with st.expander("本轮运行详情"):
                st.write(f"模型调用 {api['calls']} 次；失败 {api['failures']} 次；重试 {api['retries']} 次。")
                st.write(f"输入 {api['prompt_tokens']} / 输出 {api['completion_tokens']} tokens。")
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
        last = st.session_state.last
        if last and last.questions and last.status in ("asked", "explained"):
            choices = {q["key"]: q.get("label", q["key"]) for q in last.questions}
            choice = st.selectbox("暂时不知道哪项？", ["all", *choices],
                                  format_func=lambda k: "本轮全部问题" if k == "all" else choices[k],
                                  key=f"skip-choice:{last.session}:{last.turn}")
            if st.button("暂时跳过"):
                keys = list(choices) if choice == "all" else [choice]
                submit("这些信息暂时不清楚，先跳过。", skip_keys=keys)
                st.rerun()

    with right:
        last = st.session_state.last
        options = ["事实状态", "分析路径", "备忘录", "争点与引用", "文书", "运行轨迹"]
        default = "备忘录" if (last and last.memo) else "分析路径"
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
        elif choice == "分析路径":
            if last and last.chain:
                st.markdown(render_path_markdown(last.chain))
                if last.voi:
                    st.markdown("#### 下一步问什么：信息价值排序")
                    rows = [{"问题": schema.field_any(k).label if schema.field_any(k) else k,
                             "可区分结果数": v.get("distinct"),
                             "信息价值": v.get("gain"),
                             "说明": v.get("reason")}
                            for k, v in last.voi.items()]
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                coverage = last.coverage or {}
                if coverage:
                    st.caption(f"关键要件覆盖率：{coverage.get('known', 0)}/"
                               f"{coverage.get('total', 0)}（{coverage.get('rate', 0):.0%}）")
            else:
                st.info("还没有分析路径。先描述情况，系统会按请求权→要件→事实展开。")
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
                    content = render_legal_opinion(analysis, state, schema, last.verification)
                elif kind == "劳动仲裁申请书":
                    content = render_arbitration_application(analysis, state, schema)
                elif kind == "证据清单":
                    content = render_evidence_list(analysis, state, schema)
                elif kind == "催告函":
                    content = render_demand_letter(analysis, state, schema)
                elif kind == "被迫解除通知书":
                    content = render_forced_resignation_notice(state, schema)
                elif kind == "仲裁 vs 诉讼":
                    content = compare_arbitration_litigation(state, schema)
                else:
                    content = arbitration_checklist(state, schema)
                document_editor(content, kind)
                st.caption("以上均为草稿，需核对身份信息、金额和管辖后使用。")
        elif choice == "运行轨迹":
            if last:
                st.json(last.trace, expanded=False)


if __name__ == "__main__":
    main()

"""Markdown memorandum rendering.

The memo is organised around the element chain, not around a generic chat
summary: for each claim the reader sees which elements are established, which
are still open, which facts support them and which documents are missing.
"""
from __future__ import annotations

from datetime import datetime

from .config import DISCLAIMER
from .corpus import StatuteCorpus
from .elements import ElementSchema
from .memory import CaseState
from .rules import CLAIM_LABELS, Analysis, _cite_short

STATUS_LABEL = {
    "user_stated": "当事人陈述",
    "documentary": "材料支持",
    "verified": "已核验",
    "unknown": "尚不清楚",
    "superseded": "已被更正",
}

ELEMENT_ICON = {"satisfied": "✅", "partial": "⚠️", "unknown": "○", "blocked": "—"}
ELEMENT_TEXT = {"satisfied": "要件事实已具备", "partial": "部分具备", "unknown": "待确认",
                "blocked": "本分支不适用"}

NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
def _h(n: int, title: str) -> str:
    return f"## {NUM[n - 1] if n <= len(NUM) else n}、{title}"

NEXT_STEPS = {
    "tort_injury": [
        "道路交通事故认定书（责任划分）",
        "病历、诊断证明、医疗费与护理费票据",
        "误工证明、工资流水、纳税记录",
        "伤残鉴定意见书（如已鉴定）",
        "交强险、商业三者险保单及理赔记录",
        "居住证、租房合同、社保记录（农村户籍主张城镇标准时）",
    ],
}


def _fmt_value(value) -> str:
    if isinstance(value, float):
        return f"{value:,.0f}" if value >= 1000 else f"{value:g}"
    return str(value)


class MemoBuilder:
    def __init__(self, corpus: StatuteCorpus, schema: ElementSchema | None = None):
        self.corpus = corpus
        self.schema = schema

    # ---------------------------------------------------------------- helpers
    def _label(self, key: str) -> str:
        if self.schema:
            f = self.schema.field_any(key)
            if f:
                return f.label
        return key

    def _claim_label(self, claim: str) -> str:
        if self.schema:
            return self.schema.label(claim)
        return CLAIM_LABELS.get(claim, claim)

    # ---------------------------------------------------------------- render
    def render(self, analysis: Analysis, state: CaseState,
               verification: dict | None = None,
               llm_note: str | None = None) -> str:
        claims = analysis.metadata.get("claims") or state.claims or (
            [analysis.case_type] if analysis.case_type else [])
        lines: list[str] = []
        lines.append("# 劳动法律咨询备忘录（草稿）" if all(
            c.startswith("labor") for c in claims) else "# 法律咨询备忘录（草稿）")
        lines.append("")
        lines.append(f"- 咨询事项：{'、'.join(self._claim_label(c) for c in claims) or '未分类'}")
        lines.append(f"- 案件基准日期：{analysis.as_of or '未确定'}")
        lines.append(f"- 事实记录版本：v{state.revision}（共 {len(state.facts)} 项事实）")
        coverage = analysis.metadata.get("coverage") or {}
        if coverage:
            lines.append(f"- 关键要件覆盖率：{coverage.get('known', 0)}/"
                         f"{coverage.get('total', 0)}（{coverage.get('rate', 0):.0%}）")
        lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append(f"> {DISCLAIMER}")
        lines.append("")

        # 1) conclusion ---------------------------------------------------
        lines.append("## 一、结论摘要")
        lines.append("")
        lines.append(analysis.headline)
        lines.append("")
        if llm_note:
            lines.append("**给当事人的说明**：" + llm_note.strip())
            lines.append("")

        # 2) element chain -------------------------------------------------
        chain = analysis.metadata.get("chain") or []
        if chain:
            lines.append("## 二、分析路径：请求权 → 要件 → 事实")
            lines.append("")
            for claim in chain:
                lines.append(f"### {self._claim_label(claim['claim'])}")
                if claim.get("summary"):
                    lines.append(f"> {claim['summary']}")
                    lines.append("")
                if claim.get("basis"):
                    lines.append("**请求权基础**：" + "；".join(
                        _cite_short(c) for c in claim["basis"]))
                    lines.append("")
                if claim.get("remedy"):
                    lines.append("**可能后果**：" + claim["remedy"])
                    lines.append("")
                for i, el in enumerate(claim.get("elements", []), 1):
                    icon = ELEMENT_ICON.get(el["status"], "○")
                    lines.append(f"{i}. {icon} **{el['label']}** — "
                                 f"{ELEMENT_TEXT.get(el['status'], el['status'])}")
                    if el.get("why"):
                        lines.append(f"   - 为什么：{el['why']}")
                    known = [f for f in el.get("facts", []) if f.get("known")]
                    open_ = [f for f in el.get("facts", []) if not f.get("known")]
                    if known:
                        lines.append("   - 已具备：" + "；".join(
                            f"{f['label']}＝{_fmt_value(f['value'])}" for f in known))
                    if open_:
                        lines.append("   - 待确认：" + "、".join(
                            f["label"] for f in open_))
                lines.append("")

        # 3) facts ---------------------------------------------------------
        lines.append("## 三、事实状态")
        lines.append("")
        lines.append("| 事实 | 内容 | 状态 | 来源 | 版本 |")
        lines.append("|---|---|---|---|---|")
        for f in sorted(state.facts.values(), key=lambda x: -x.revision):
            if f.superseded_by is not None:
                continue
            lines.append(f"| {self._label(f.key)} | {_fmt_value(f.value)} | "
                         f"{STATUS_LABEL.get(f.status, f.status)} | {f.source} | v{f.revision} |")
        if state.history:
            lines.append("")
            lines.append("**已被更正的事实**（旧值不再作为结论依据）：")
            for h in state.history:
                lines.append(f"- {self._label(h.key)}：~~{_fmt_value(h.value)}~~ → "
                             f"v{h.superseded_by}")
        if state.known_unknowns:
            lines.append("")
            lines.append("**当事人明确表示不清楚的事实**：" +
                         "、".join(self._label(k) for k in state.known_unknowns))
        lines.append("")

        # 4) issues --------------------------------------------------------
        lines.append("## 四、争点分析")
        lines.append("")
        if not analysis.findings:
            lines.append("（暂无可分析的争点，需补充事实。）")
        for i, finding in enumerate(analysis.findings, 1):
            lines.append(f"### {i}. {finding.issue}　`风险：{finding.risk}`")
            lines.append("")
            lines.append(f"**结论**：{finding.conclusion}")
            lines.append("")
            lines.append(f"**理由**：{finding.reasoning}")
            lines.append("")
            if finding.cites:
                cites = "；".join(_cite_short(c) for c in finding.cites)
                lines.append(f"**依据**：{cites}")
                lines.append("")
            if finding.assumptions:
                lines.append("**适用前提**：" + "；".join(finding.assumptions))
                lines.append("")

        # 5) calculations --------------------------------------------------
        per_claim = analysis.metadata.get("per_claim") or {}
        calcs = [(c, m.get("calculation")) for c, m in per_claim.items()
                 if isinstance(m, dict) and m.get("calculation")]
        n_notes = 6 if calcs else 5
        if calcs:
            lines.append("## 五、金额计算")
            lines.append("")
            for claim, calc in calcs:
                if not calc or not calc.get("ok"):
                    continue
                lines.append(f"- **{self._claim_label(claim)}**：{calc.get('formula')}，"
                             f"合计约 **{calc.get('amount', 0):,.0f} 元**")
                for a in calc.get("assumptions", []):
                    lines.append(f"  - 假设：{a}")
            lines.append("")

        # 6) practice notes ------------------------------------------------
        notes = analysis.metadata.get("practice_notes") or []
        if notes:
            lines.append(_h(n_notes, "实务提示（RAG 检索：法院/人社口径）"))
            lines.append("")
            for n in notes[:4]:
                lines.append(f"**{n.get('title')}**（{n.get('publisher')}，{n.get('date')}）")
                for p in n.get("points", [])[:4]:
                    lines.append(f"- {p}")
                if n.get("caveat"):
                    lines.append(f"- 注意：{n['caveat']}")
                if n.get("score"):
                    lines.append(f"- 检索相关度：BM25 {n['score']}")
                lines.append(f"- 来源：[{n.get('url')}]({n.get('url')})")
                lines.append("")

        # 7) gaps ----------------------------------------------------------
        lines.append(_h(n_notes + 1, "信息缺口与不确定"))
        lines.append("")
        if analysis.gaps:
            for g in analysis.gaps:
                lines.append(f"- {g}")
        else:
            lines.append("- 关键要件事实已基本齐备；仍可能存在证据真伪与证明力问题。")
        for a in analysis.assumptions:
            lines.append(f"- 假设：{a}")
        lines.append("")

        # 8) evidence ------------------------------------------------------
        checklist = analysis.metadata.get("proof_checklist") or []
        lines.append(_h(n_notes + 2, "下一步与证据清单"))
        lines.append("")
        if checklist:
            lines.append("**按要件整理的证据清单：**")
            for item in checklist:
                lines.append(f"- [ ] {item}")
            lines.append("")
        for s in NEXT_STEPS.get(analysis.case_type, []):
            if not checklist:
                lines.append(f"- [ ] {s}")
        lines.append("**程序建议：**")
        lines.append("- [ ] 先核对仲裁时效与管辖，再决定申请仲裁还是先投诉/协商。")
        lines.append("- [ ] 与单位沟通尽量留书面记录；录音、微信记录注意保留原始载体。")
        lines.append("- [ ] 如涉及工伤，先确认工伤认定和劳动能力鉴定的进度。")
        lines.append("")

        # 9) citations -----------------------------------------------------
        lines.append(_h(n_notes + 3, "引用与版本"))
        lines.append("")
        lines.append("| 法条 | 生效期间 | 原文摘录 | 来源 |")
        lines.append("|---|---|---|---|")
        used: list[str] = []
        for f in analysis.findings:
            used.extend(f.cites)
        for aid in dict.fromkeys(used):
            art = self.corpus.get(aid)
            if not art:
                continue
            excerpt = art.text.replace("\n", " ")[:80]
            lines.append(f"| {art.citation} | {art.valid_from} ~ "
                         f"{'现行' if art.valid_to > '2099-01-01' else art.valid_to} | "
                         f"{excerpt}… | [源]({art.source}) |")
        lines.append("")

        if verification:
            lines.append("## 附：自动核验")
            lines.append("")
            lines.append(f"- 结论条目：{verification['checked']}，通过核验："
                         f"{verification['supported']}（支持率 {verification['support_rate']:.0%}）")
            if verification["defects"]:
                for d in verification["defects"]:
                    lines.append(f"- `{d['code']}` {d['claim_id']}：{d['detail']}")
            else:
                lines.append("- 未发现引用缺失、版本失效、引文不符或事实过期问题。")
            lines.append("- 说明：自动核验只能检查引用是否存在、是否有效、引文是否对得上、"
                         "所依赖事实是否仍为最新；它不能证明法律论证本身正确。")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

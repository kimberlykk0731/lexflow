"""Markdown memorandum rendering."""
from __future__ import annotations

from datetime import datetime

from .config import DISCLAIMER
from .corpus import StatuteCorpus
from .memory import CaseState
from .rules import Analysis, _cite_short

STATUS_LABEL = {
    "user_stated": "当事人陈述",
    "documentary": "材料支持",
    "verified": "已核验",
    "unknown": "尚不清楚",
    "superseded": "已被更正",
}

NEXT_STEPS = {
    "labor_dismissal": [
        "解除劳动合同通知书、微信/邮件通知或通话录音（确定解除日期、主体与理由）",
        "劳动合同、入职登记表、考勤记录（证明劳动关系与工作年限）",
        "员工手册、规章制度文本及签收/培训/公示记录",
        "公司据以认定违纪的证据（监控、书面检讨、证人、处理决定）",
        "解除前十二个月工资流水、社保缴纳记录（计算基数）",
        "工会通知或征求意见的记录（如公司设有工会）",
        "如已申请仲裁：仲裁受理通知书与开庭通知",
    ],
    "tort_injury": [
        "道路交通事故认定书（责任划分）",
        "病历、诊断证明、医疗费与护理费票据",
        "误工证明、工资流水、纳税记录",
        "伤残鉴定意见书（如已鉴定）",
        "交强险、商业三者险保单及理赔记录",
        "居住证、租房合同、社保记录（农村户籍主张城镇标准时）",
        "事故认定复核申请材料（如对责任认定有异议）",
    ],
}


def _fmt_value(value) -> str:
    if isinstance(value, float):
        return f"{value:,.0f}" if value >= 1000 else f"{value:g}"
    return str(value)


class MemoBuilder:
    def __init__(self, corpus: StatuteCorpus):
        self.corpus = corpus

    def render(self, analysis: Analysis, state: CaseState,
               verification: dict | None = None,
               llm_note: str | None = None) -> str:
        ct_label = {
            "labor_dismissal": "劳动争议 · 解除劳动合同",
            "tort_injury": "侵权 · 交通事故人身损害",
        }.get(analysis.case_type, analysis.case_type)
        lines: list[str] = []
        lines.append("# 法律咨询备忘录（草稿）")
        lines.append("")
        lines.append(f"- 案由：{ct_label}")
        lines.append(f"- 案件基准日期：{analysis.as_of or '未确定'}")
        lines.append(f"- 事实记录版本：v{state.revision}（共 {len(state.facts)} 项事实）")
        lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append(f"> {DISCLAIMER}")
        lines.append("")

        lines.append("## 一、结论摘要")
        lines.append("")
        lines.append(analysis.headline)
        lines.append("")
        if llm_note:
            lines.append("**给当事人的说明**：" + llm_note.strip())
            lines.append("")

        lines.append("## 二、事实状态")
        lines.append("")
        lines.append("| 事实 | 内容 | 状态 | 来源 | 版本 |")
        lines.append("|---|---|---|---|---|")
        for f in sorted(state.facts.values(), key=lambda x: -x.revision):
            if f.superseded_by is not None:
                continue
            lines.append(f"| {f.key} | {_fmt_value(f.value)} | "
                         f"{STATUS_LABEL.get(f.status, f.status)} | {f.source} | v{f.revision} |")
        if state.history:
            lines.append("")
            lines.append("**已被更正的事实**（旧值不再作为结论依据）：")
            for h in state.history:
                lines.append(f"- {h.key}：~~{_fmt_value(h.value)}~~ → v{h.superseded_by}")
        if state.known_unknowns:
            lines.append("")
            lines.append("**当事人明确表示不清楚的事实**：" +
                         "、".join(state.known_unknowns))
        lines.append("")

        lines.append("## 三、争点分析")
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

        lines.append("## 四、信息缺口与不确定")
        lines.append("")
        if analysis.gaps:
            for g in analysis.gaps:
                lines.append(f"- {g}")
        else:
            lines.append("- 关键要件事实已基本齐备；仍可能存在证据真伪与证明力问题。")
        for a in analysis.assumptions:
            lines.append(f"- 假设：{a}")
        lines.append("")

        lines.append("## 五、下一步与所需材料")
        lines.append("")
        for s in NEXT_STEPS.get(analysis.case_type, []):
            lines.append(f"- {s}")
        lines.append("")

        lines.append("## 六、引用与版本")
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

"""Render the analysis path: claim basis → element → fact → proof.

This is the visible counterpart of the element tree.  The same structure is
used by the CLI demo, the Streamlit panel and the memo, so the "why" behind a
question is not buried in the trace.
"""
from __future__ import annotations

from .rules import _cite_short

ICON = {"satisfied": "✅", "partial": "⚠️", "unknown": "○", "blocked": "—"}
STATUS_CN = {"satisfied": "已具备", "partial": "部分具备",
             "unknown": "待确认", "blocked": "本分支不适用"}


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:,.0f}"
    return str(value)


def render_path_text(chain: list[dict], indent: str = "  ") -> str:
    lines: list[str] = []
    for claim in chain or []:
        lines.append(f"【请求权】{claim.get('label', claim.get('claim', ''))}")
        if claim.get("basis"):
            lines.append(indent + "请求权基础：" + "；".join(_cite_short(c)
                                                        for c in claim["basis"]))
        if claim.get("remedy"):
            lines.append(indent + "可能后果：" + claim["remedy"])
        for el in claim.get("elements", []):
            icon = ICON.get(el.get("status"), "○")
            lines.append(f"{indent}{icon} 要件：{el.get('label', '')}"
                         f"（{STATUS_CN.get(el.get('status'), el.get('status', ''))}）")
            for fact in el.get("facts", []):
                mark = "✓" if fact.get("known") else "?"
                value = f" = {_fmt(fact.get('value'))}" if fact.get("known") else ""
                lines.append(f"{indent}  {mark} {fact.get('label', '')}{value}")
            if el.get("proof"):
                lines.append(f"{indent}   证据：{'、'.join(el['proof'])}")
    return "\n".join(lines)


def render_path_markdown(chain: list[dict]) -> str:
    lines: list[str] = []
    for claim in chain or []:
        lines.append(f"### 请求权：{claim.get('label', claim.get('claim', ''))}")
        lines.append("")
        if claim.get("basis"):
            lines.append("**请求权基础**：" + "；".join(_cite_short(c)
                                                     for c in claim["basis"]))
        if claim.get("remedy"):
            lines.append("")
            lines.append("**可能后果**：" + claim["remedy"])
        lines.append("")
        for el in claim.get("elements", []):
            icon = ICON.get(el.get("status"), "○")
            lines.append(f"- {icon} **{el.get('label', '')}** — "
                         f"{STATUS_CN.get(el.get('status'), el.get('status', ''))}")
            if el.get("why"):
                lines.append(f"  - 为什么：{el['why']}")
            known = [f for f in el.get("facts", []) if f.get("known")]
            open_ = [f for f in el.get("facts", []) if not f.get("known")]
            if known:
                lines.append("  - 已具备：" + "；".join(
                    f"{f['label']}＝{_fmt(f['value'])}" for f in known))
            if open_:
                lines.append("  - 待确认：" + "、".join(f["label"] for f in open_))
            if el.get("proof"):
                lines.append("  - 证据：" + "、".join(el["proof"]))
        lines.append("")
    return "\n".join(lines).strip()


def render_question_path(question, facts: dict) -> str:
    """One-line explanation of why this question is next."""
    bits = [f"要件「{question.element_label}」", f"需要事实「{question.field.label}」"]
    if question.field.why:
        bits.append(question.field.why)
    return "；".join(bits)

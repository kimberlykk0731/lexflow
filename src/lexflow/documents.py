"""Document generators for worker-facing deliverables.

The chat reply is a summary; these are the artifacts a worker can actually use:

* 法律意见书  — structured opinion with facts, analysis, conclusion, limits;
* 劳动仲裁申请书 — request items, facts, evidence, addressee;
* 证据清单    — element-by-element evidence checklist;
* 律师函/催告函 — demand letter skeleton;
* 被迫解除通知书 — art. 38 notice skeleton.

All outputs are drafts with blanks for identity details.  They never invent a
party name, amount, case number or court.
"""
from __future__ import annotations

from datetime import date

from .elements import ElementSchema
from .memory import CaseState
from .rules import Analysis, CLAIM_LABELS, _cite_short


def _value(state: CaseState, key: str, default: str = "________") -> str:
    v = state.value(key)
    if v in (None, "", "不清楚", "记不清", "说不清"):
        return default
    if isinstance(v, float):
        return f"{v:,.0f}"
    return str(v)


def _label(schema: ElementSchema, key: str) -> str:
    f = schema.field_any(key)
    return f.label if f else key


def _claim_label(schema: ElementSchema, claim: str) -> str:
    return schema.label(claim) if claim in schema.types() else CLAIM_LABELS.get(claim, claim)


def _calc(analysis: Analysis, claim: str) -> dict | None:
    per = (analysis.metadata or {}).get("per_claim", {})
    meta = per.get(claim) or {}
    return meta.get("calculation") if isinstance(meta, dict) else None


def _compensation(analysis: Analysis) -> dict | None:
    meta = analysis.metadata or {}
    comp = meta.get("compensation")
    if comp:
        return comp
    for m in (meta.get("per_claim") or {}).values():
        if isinstance(m, dict) and m.get("compensation"):
            return m["compensation"]
    return None


def _amount(analysis: Analysis, claim: str, state: CaseState | None = None) -> float | None:
    calc = _calc(analysis, claim)
    if calc and calc.get("ok"):
        return float(calc.get("amount") or 0)
    if claim == "labor_dismissal":
        comp = _compensation(analysis)
        if comp and comp.get("ok"):
            return float(comp.get("amount") or 0)
    if state is not None and claim == "labor_wage":
        v = state.value("wage_owed")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _requests(analysis: Analysis, state: CaseState,
              schema: ElementSchema) -> list[str]:
    claims = state.claims or list((analysis.metadata or {}).get("per_claim", {}))
    reqs: list[str] = []
    for claim in claims:
        amount = _amount(analysis, claim, state)
        if claim == "labor_dismissal":
            comp = _compensation(analysis)
            if comp and comp.get("ok"):
                kind = "违法解除赔偿金（2N）" if comp.get("multiplier") == 2 else "经济补偿（N）"
                reqs.append(f"请求裁决被申请人支付{kind} {amount:,.0f} 元"
                            f"（{comp.get('formula')}）。")
            else:
                reqs.append("请求裁决被申请人支付违法解除劳动合同赔偿金（金额待核定）。")
        elif claim == "labor_wage":
            reqs.append(f"请求裁决被申请人支付拖欠工资 {amount:,.0f} 元。"
                        if amount else "请求裁决被申请人支付拖欠工资（金额待核定）。")
        elif claim == "labor_overtime":
            reqs.append(f"请求裁决被申请人支付加班费 {amount:,.0f} 元。"
                        if amount else "请求裁决被申请人支付加班费（金额待核定）。")
        elif claim == "labor_double_pay":
            reqs.append(f"请求裁决被申请人支付未签书面劳动合同二倍工资差额 {amount:,.0f} 元。"
                        if amount else "请求裁决被申请人支付未签书面劳动合同二倍工资差额。")
        elif claim == "labor_work_injury":
            reqs.append("请求裁决被申请人支付工伤保险待遇（一次性伤残补助金等，金额待核定）。")
        elif claim == "labor_annual_leave":
            reqs.append(f"请求裁决被申请人支付未休年假工资 {amount:,.0f} 元。"
                        if amount else "请求裁决被申请人支付未休年假工资。")
        elif claim == "labor_noncompete":
            reqs.append(f"请求裁决被申请人支付竞业限制补偿 {amount:,.0f} 元。"
                        if amount else "请求裁决被申请人支付竞业限制补偿。")
        elif claim == "labor_social_insurance":
            reqs.append("请求裁决被申请人支付未依法缴纳社会保险费造成的损失/被迫解除经济补偿"
                        "（补缴部分另向社保征收机构投诉）。")
        elif claim == "labor_maternity":
            reqs.append("请求裁决被申请人支付产假工资/生育津贴差额及违法解除赔偿。")
        elif claim == "labor_dispatch":
            reqs.append("请求确认申请人与被申请人存在劳动关系，并支付相应劳动报酬/工伤待遇。")
        elif claim == "labor_contract":
            reqs.append("请求裁决被申请人补签书面劳动合同/确认无固定期限劳动关系/补足工资差额。")
        elif claim == "labor_procedure":
            continue
        elif claim == "tort_injury":
            reqs.append("请求判令被告赔偿医疗费、误工费、护理费、残疾赔偿金等（金额待核定）。")
    if not reqs:
        reqs.append("请求裁决被申请人承担相应的劳动法律责任（具体请求待补充）。")
    return reqs


def render_legal_opinion(analysis: Analysis, state: CaseState, schema: ElementSchema,
                         verification: dict | None = None) -> str:
    claims = state.claims or [analysis.case_type]
    lines = [
        "# 法律意见书（草稿）",
        "",
        f"**致：** {_value(state, 'client_name', '________（委托人）')}",
        f"**出具日期：** {date.today().isoformat()}",
        f"**事项：** {'、'.join(_claim_label(schema, c) for c in claims)}",
        "",
        "> 本意见书基于委托人目前提供的事实和材料作出，不构成对裁判结果的承诺。"
        "身份信息、金额和证据需由委托人核对后补全。",
        "",
        "## 一、事实摘要",
        "",
    ]
    for key in ("employer", "start_date", "dismiss_date", "monthly_wage", "position",
                "work_location", "injury_date", "accident_date"):
        if state.value(key) not in (None, ""):
            lines.append(f"- {_label(schema, key)}：{_value(state, key)}")
    lines.append("")
    lines.append("## 二、法律分析")
    lines.append("")
    if not analysis.findings:
        lines.append("现有事实不足以形成确定性分析，需补充要件事实。")
    for i, f in enumerate(analysis.findings, 1):
        lines.append(f"### （{i}）{f.issue}")
        lines.append("")
        lines.append(f.conclusion)
        lines.append("")
        lines.append(f"理由：{f.reasoning}")
        if f.cites:
            lines.append("")
            lines.append("依据：" + "；".join(_cite_short(c) for c in f.cites))
        lines.append("")
    lines.append("## 三、结论")
    lines.append("")
    lines.append(analysis.headline)
    lines.append("")
    lines.append("## 四、请求/建议")
    lines.append("")
    for r in _requests(analysis, state, schema):
        lines.append(f"1. {r}")
    lines.append("1. 先核对仲裁时效、管辖和证据原件，再决定申请仲裁或协商。")
    lines.append("")
    lines.append("## 五、风险与限制")
    lines.append("")
    for g in (analysis.gaps or ["尚未发现明显缺口，但仍需核对证据真实性。"]):
        lines.append(f"- {g}")
    for a in analysis.assumptions:
        lines.append(f"- 假设：{a}")
    lines.append("")
    lines.append("## 六、声明")
    lines.append("")
    lines.append("本意见书为系统生成的草稿，仅供委托人内部参考，不构成正式法律意见，"
                 "也不替代执业律师根据全部证据作出的判断。")
    lines.append("")
    if verification:
        lines.append(f"（自动核验：{verification.get('supported', 0)}/"
                     f"{verification.get('checked', 0)} 条结论通过引用核验。）")
    return "\n".join(lines)


def render_arbitration_application(analysis: Analysis, state: CaseState,
                                   schema: ElementSchema) -> str:
    claims = state.claims or [analysis.case_type]
    reqs = _requests(analysis, state, schema)
    lines = [
        "# 劳动人事争议仲裁申请书（草稿）",
        "",
        "**申请人：** ________（姓名、性别、出生日期、身份证号、住址、联系电话）",
        "**被申请人：** " + _value(state, "employer", "________（单位全称）"),
        "**被申请人住所地：** ________",
        "**法定代表人/负责人：** ________",
        "",
        "## 仲裁请求",
        "",
    ]
    for i, r in enumerate(reqs, 1):
        lines.append(f"{i}. {r}")
    lines += ["", "## 事实与理由", ""]
    lines.append(f"申请人于 {_value(state, 'start_date')} 入职被申请人处，"
                 f"岗位为 {_value(state, 'position')}，月平均工资约 "
                 f"{_value(state, 'monthly_wage')} 元。")
    if state.value("dismiss_date"):
        lines.append(f"{_value(state, 'dismiss_date')}，被申请人"
                     f"{'单方解除劳动合同' if state.value('who_initiated') == '单位单方解除' else '终止用工'}。")
    lines.append("")
    lines.append(analysis.headline)
    lines.append("")
    for f in analysis.findings:
        lines.append(f"- {f.issue}：{f.conclusion}")
    lines += ["", "## 证据清单", ""]
    checklist = (analysis.metadata or {}).get("proof_checklist") or []
    for i, item in enumerate(checklist, 1):
        lines.append(f"{i}. {item}")
    lines += [
        "",
        "此致",
        "",
        "________劳动人事争议仲裁委员会",
        "",
        "申请人（签名）：________",
        f"日期：{date.today().isoformat()}",
        "",
        "> 草稿：管辖、请求金额、身份信息和证据份数需按当地仲裁委要求核对。",
    ]
    return "\n".join(lines)


def render_evidence_list(analysis: Analysis, state: CaseState,
                         schema: ElementSchema) -> str:
    claims = state.claims or [analysis.case_type]
    lines = ["# 证据清单（草稿）", "",
             f"**事项：** {'、'.join(_claim_label(schema, c) for c in claims)}", ""]
    chain = (analysis.metadata or {}).get("chain") or []
    for claim in chain:
        lines.append(f"## {_claim_label(schema, claim['claim'])}")
        lines.append("")
        for el in claim.get("elements", []):
            if el.get("status") == "blocked":
                continue
            status = {"satisfied": "已具备", "partial": "部分具备",
                      "unknown": "待确认", "blocked": "不适用"}.get(el["status"], el["status"])
            lines.append(f"### {el['label']}（{status}）")
            for item in el.get("proof", []):
                lines.append(f"- [ ] {item}：________")
            lines.append("")
    lines.append("## 通用材料")
    for item in ("身份证复印件", "仲裁申请书（按被申请人人数+1份）",
                 "用人单位工商登记信息", "授权委托书（如委托代理人）"):
        lines.append(f"- [ ] {item}")
    lines.append("")
    lines.append("> 草稿：证据原件/复印件份数、是否需要公证或翻译，按仲裁委要求准备。")
    return "\n".join(lines)


def render_demand_letter(analysis: Analysis, state: CaseState,
                         schema: ElementSchema) -> str:
    lines = [
        "# 律师函/催告函（草稿）",
        "",
        f"**致：** {_value(state, 'employer', '________（单位全称）')}",
        "",
        "本函就贵司与________（下称“委托人”）之间的劳动用工事宜，郑重函告如下：",
        "",
    ]
    for i, r in enumerate(_requests(analysis, state, schema), 1):
        lines.append(f"{i}. {r}")
    lines += [
        "",
        "请贵司自收到本函之日起 ________ 日内书面回复并履行上述义务；"
        "逾期未处理的，委托人将依法向劳动人事争议仲裁委员会申请仲裁，"
        "并向劳动保障监察机构投诉。",
        "",
        "本函不构成对任何权利的放弃。",
        "",
        "________律师事务所",
        "律师：________",
        f"{date.today().isoformat()}",
        "",
        "> 草稿：需由执业律师审核并加盖律所公章后发出。",
    ]
    return "\n".join(lines)


def render_forced_resignation_notice(state: CaseState, schema: ElementSchema) -> str:
    reason = state.value("forced_resignation_reason") or "________"
    lines = [
        "# 被迫解除劳动合同通知书（草稿）",
        "",
        f"**致：** {_value(state, 'employer', '________（单位全称）')}",
        "",
        "本人________，于 " + _value(state, "start_date") + " 入职贵司，"
        "现因贵司存在以下情形：",
        "",
        f"1. {reason}；",
        "",
        "根据《中华人民共和国劳动合同法》第三十八条，本人自即日起解除与贵司的劳动合同，"
        "并保留依法主张经济补偿、欠付工资、加班费、未休年假工资等权利。",
        "",
        "请贵司在解除之日起十五日内为本人办理档案和社会保险关系转移手续，"
        "并依法支付经济补偿及结清工资。",
        "",
        "通知人（签名）：________",
        f"日期：{date.today().isoformat()}",
        "",
        "> 草稿：解除理由必须与事实和证据对应；建议通过 EMS、邮件等可留痕方式送达。",
    ]
    return "\n".join(lines)

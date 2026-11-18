"""Deterministic legal analysis layer.

Rules that are arithmetic or definitional (limitation periods, compensation,
which version of an interpretation applies) are implemented in code and
covered by tests.  Open-textual judgement (how to phrase a question, how to
write the memo) is left to the model.  This split keeps the demo auditable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .elements import parse_date


@dataclass
class Finding:
    id: str
    issue: str
    conclusion: str
    reasoning: str
    cites: list[str]
    depends: list[str] = field(default_factory=list)
    risk: str = "不确定"
    quote: str = ""
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Analysis:
    case_type: str
    as_of: str
    headline: str
    findings: list[Finding]
    gaps: list[str]
    assumptions: list[str]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["findings"] = [f.to_dict() for f in self.findings]
        return d


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 2/29
        return d.replace(year=d.year + years, day=28)


def _cite_short(article_id: str) -> str:
    law, _, rest = article_id.partition("@")
    article = rest.split(":", 1)[1] if ":" in rest else ""
    names = {
        "labor_contract": "《劳动合同法》", "labor_law": "《劳动法》",
        "labor_dispute": "《劳动争议调解仲裁法》",
        "labor_contract_regs": "《劳动合同法实施条例》",
        "labor_js1": "《劳动争议司法解释（一）》",
        "civil_code_general": "《民法典》", "civil_code_tort": "《民法典》",
        "tort_interp_2003": "《人身损害赔偿解释（2003）》",
        "tort_interp_2020": "《人身损害赔偿解释（2020）》",
        "tort_interp_2022": "《人身损害赔偿解释（2022）》",
        "civil_time_effect": "《民法典时间效力规定》",
        "road_traffic": "《道路交通安全法》",
    }
    return f"{names.get(law, law)}{article}"


def first_sentence(text: str, limit: int = 60) -> str:
    text = re.sub(r"\s+", "", text or "")
    for sep in ("。", "；"):
        if sep in text:
            return text.split(sep)[0][:limit]
    return text[:limit]


# --------------------------------------------------------------------- 时效
def check_limitation(case_type: str, anchor: str, today: str | None = None) -> dict:
    """Compute the limitation period from the anchor date.

    labour: 1 year from the date the right was known to be infringed
            (60 days before the 2008-05-01 entry into force of the
            Mediation and Arbitration Act).
    tort:   3 years under Civil Code art. 188.
    """
    d = parse_date(anchor)
    if not d:
        return {"ok": False, "reason": "缺少可解析的起算日期"}
    today_d = parse_date(today) if today else date.today()

    if case_type == "labor_dismissal":
        if d < date(2008, 5, 1):
            deadline = d + timedelta(days=60)
            basis = "labor_law@1995-01-01:第82条"
            label = "60日（劳动法第82条，适用于2008-05-01前的争议）"
            days = 60
        else:
            deadline = add_years(d, 1)
            basis = "labor_dispute@2008-05-01:第27条"
            label = "1年（劳动争议调解仲裁法第27条）"
            days = 365
        return {
            "ok": True, "kind": "仲裁时效", "start": d.isoformat(),
            "deadline": deadline.isoformat(), "basis": basis, "label": label,
            "expired": today_d > deadline,
            "days_left": (deadline - today_d).days,
            "note": "期间自当事人知道或者应当知道权利被侵害之日起计算；"
                    "以解除通知送达/解除之日为起算点属于常见但需核实的选择。",
        }

    if d < date(2017, 10, 1):
        deadline = add_years(d, 1)
        basis = "general_principles_civil_law@1987-01-01:第136条"
        label = "1年（民法通则第136条，身体受到伤害）"
        note = "2017-10-01 前，身体受到伤害的诉讼时效为一年；此后改为三年。"
    elif d < date(2021, 1, 1):
        deadline = add_years(d, 3)
        basis = "civil_general_principles@2017-10-01:第188条"
        label = "3年（民法总则第188条）"
        note = "2017-10-01 至 2020-12-31 期间适用民法总则的三年诉讼时效。"
    else:
        deadline = add_years(d, 3)
        basis = "civil_code_general@2021-01-01:第188条"
        label = "3年（民法典第188条）"
        note = "民法典施行后适用三年诉讼时效。"
    return {
        "ok": True, "kind": "诉讼时效", "start": d.isoformat(),
        "deadline": deadline.isoformat(), "basis": basis,
        "label": label, "expired": today_d > deadline,
        "days_left": (deadline - today_d).days,
        "note": note + " 人身损害案件的起算点可能为确诊、治疗终结或伤残鉴定之日，"
                "以事故发生日起算仅为简化假设。",
    }


# ----------------------------------------------------------------- 经济补偿
def work_years(start: str, end: str) -> dict:
    s, e = parse_date(start), parse_date(end)
    if not s or not e or e < s:
        return {"ok": False, "reason": "入职或解除日期无效"}
    years = e.year - s.year
    anniversary = add_years(s, years)
    if anniversary > e:
        years -= 1
        anniversary = add_years(s, years)
    months = (e.year - anniversary.year) * 12 + (e.month - anniversary.month)
    if e.day < anniversary.day:
        months -= 1
    months = max(months, 0)
    if months == 0:
        n = float(years)
        rule = "每满一年支付一个月工资"
    elif months < 6:
        n = years + 0.5
        rule = "不满六个月支付半个月工资"
    else:
        n = years + 1
        rule = "六个月以上不满一年按一年计算"
    return {"ok": True, "years": years, "extra_months": months, "n": n,
            "rule": rule, "total_label": f"{years}年{months}个月"}


def compute_compensation(facts: dict, pay_type: str = "N",
                         extra_notice: bool = False) -> dict:
    """Compute 0 / N / N+1 / 2N.

    pay_type:
        "0"  — lawful dismissal under art. 39 (serious misconduct) or resignation
        "N"  — economic compensation under arts. 46/47
        "2N" — unlawful dismissal damages under art. 87
    """
    start, end = facts.get("start_date"), facts.get("dismiss_date")
    wage = facts.get("monthly_wage")
    wy = work_years(start, end) if start and end else {"ok": False}
    if not isinstance(wage, (int, float)) or wage <= 0:
        return {"ok": False, "missing": ["monthly_wage（需为数字）"]}
    if not wy.get("ok"):
        missing = [k for k in ("start_date", "dismiss_date", "monthly_wage") if not facts.get(k)]
        return {"ok": False, "missing": missing}
    n = wy["n"]
    if n <= 0:
        return {"ok": False, "missing": ["有效工作年限（入职日期应早于解除日期）"]}
    base = float(wage)
    if pay_type == "0":
        return {
            "ok": True, "n": 0.0, "base": base, "multiplier": 0,
            "amount": 0.0, "formula": "合法解除且属于《劳动合同法》第39条情形，无需支付经济补偿",
            "work_years_label": wy["total_label"], "years_rule": wy["rule"],
            "cites": ["labor_contract@2008-01-01:第39条", "labor_contract@2008-01-01:第46条"],
            "assumptions": ["第39条解除无需支付经济补偿；此处仍列出工作年限，便于核对。"],
        }
    multiplier = 2 if pay_type == "2N" else 1
    months = n + (1 if extra_notice else 0)
    amount = base * months * multiplier
    formula = f"{base:,.0f} 元/月 × {months:g} 个月" + (" × 2（违法解除赔偿金）" if multiplier == 2 else "")
    if extra_notice:
        formula += "（含一个月代通知金）"
    return {
        "ok": True, "n": n, "months": months, "base": base, "multiplier": multiplier,
        "amount": round(amount, 2), "formula": formula,
        "work_years_label": wy["total_label"], "years_rule": wy["rule"],
        "cites": ["labor_contract@2008-01-01:第47条",
                  "labor_contract@2008-01-01:第87条" if multiplier == 2
                  else "labor_contract@2008-01-01:第46条"],
        "assumptions": [
            "月工资按解除前十二个月平均应发工资计算，实践中的奖金、补贴是否计入存在争议。",
            "若月工资高于用人单位所在设区的市级人民政府公布的上年度职工月平均工资三倍，"
            "则按三倍封顶且年限不超过十二年；本项目未接入当地社平工资数据，需人工核对。",
        ],
    }


# --------------------------------------------------------------- 解除合法性
def assess_dismissal(facts: dict, today: str | None = None,
                     revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    assumptions: list[str] = []
    reason = facts.get("stated_reason") or "其他或说不清"
    who = facts.get("who_initiated") or "说不清"
    illegal_flag = False
    confidence = "不确定"

    # 1) 时效先行：这是律师接案的第一道门槛
    lim = check_limitation("labor_dismissal", facts.get("dismiss_date", ""), today)
    if lim.get("ok"):
        findings.append(Finding(
            id="F_LIMITATION", issue="仲裁时效",
            conclusion=(f"{lim['label']}，自 {lim['start']} 起算，"
                        f"届满日为 {lim['deadline']}；"
                        + ("已超过一年，对方很可能提出时效抗辩；需核查是否存在中断、中止事由。"
                           if lim["expired"] else f"目前尚未届满（剩余约 {lim['days_left']} 天）。")),
            reasoning=lim["note"],
            cites=[lim["basis"]],
            depends=["dismiss_date"],
            risk="高" if lim["expired"] else "中",
            assumptions=["以解除日为时效起算点"] if lim["basis"].startswith("labor_dispute") else [],
        ))
        if lim["expired"]:
            gaps.append("时效可能已过：需核实是否存在向单位主张权利、投诉、调解等中断事由。")
    else:
        gaps.append("缺少解除日期，无法判断仲裁时效。")

    # 2) 解除性质
    if who == "劳动者辞职":
        findings.append(Finding(
            id="F_NATURE", issue="解除性质",
            conclusion="劳动者主动辞职，原则上不产生经济补偿；但若属于用人单位违法在先、劳动者依第38条被迫解除，仍可主张经济补偿。",
            reasoning="辞职与被迫解除的法律后果不同，需核查是否存在欠薪、未缴社保等情形。",
            cites=["labor_contract@2008-01-01:第38条", "labor_contract@2008-01-01:第46条"],
            depends=["who_initiated"], risk="中",
        ))
        confidence = "需进一步核查"
    elif who == "协商一致解除":
        findings.append(Finding(
            id="F_NATURE", issue="解除性质",
            conclusion="协商一致解除，若由用人单位提出，应支付经济补偿（N）；若由劳动者提出，一般无补偿。",
            reasoning="第46条第（二）项仅覆盖用人单位提出并协商一致的情形。",
            cites=["labor_contract@2008-01-01:第36条", "labor_contract@2008-01-01:第46条"],
            depends=["who_initiated"], risk="中",
        ))
    else:
        # 3) 严重违纪分支
        if reason == "严重违纪":
            publicized = facts.get("rule_publicized")
            exists = facts.get("rule_exists")
            democratic = facts.get("rule_democratic")
            proof = facts.get("misconduct_proof")
            union = facts.get("union_notified")

            if publicized == "没有公示告知":
                illegal_flag = True
                findings.append(Finding(
                    id="F_RULE_PUBLICITY", issue="规章制度的公示告知",
                    conclusion="若公司不能证明已向劳动者公示或告知规章制度，该制度原则上不能作为解除依据，解除被认定违法的风险高。",
                    reasoning="直接涉及劳动者切身利益的规章制度应当公示或者告知劳动者；"
                              "经民主程序制定并已公示的制度才可作为审理依据。",
                    cites=["labor_contract@2008-01-01:第4条", "labor_js1@2021-01-01:第50条"],
                    depends=["rule_publicized", "stated_reason"], risk="高",
                ))
            elif publicized in ("有签收或公示",):
                findings.append(Finding(
                    id="F_RULE_PUBLICITY", issue="规章制度的公示告知",
                    conclusion="规章制度已公示或告知，公示环节的违法风险较低；争点转向制度内容是否合法、违纪事实是否成立。",
                    reasoning="有签收或公示记录时，法院通常认可制度可作为依据，但仍审查内容合法性与程序。",
                    cites=["labor_contract@2008-01-01:第4条", "labor_js1@2021-01-01:第50条"],
                    depends=["rule_publicized"], risk="低",
                ))
            else:
                gaps.append("规章制度是否公示告知尚不明确，这是严重违纪解除的核心争点。")

            if exists == "没有成文制度":
                illegal_flag = True
                findings.append(Finding(
                    id="F_RULE_EXISTS", issue="规章制度依据",
                    conclusion="公司没有成文的规章制度，以“严重违纪”解除缺少规范依据，违法解除风险高。",
                    reasoning="严重违纪以违反用人单位规章制度为前提，无制度则难以成立。",
                    cites=["labor_contract@2008-01-01:第39条"],
                    depends=["rule_exists"], risk="高",
                ))

            if democratic == "没有经过":
                findings.append(Finding(
                    id="F_RULE_PROCEDURE", issue="规章制度的制定程序",
                    conclusion="制度未经职工代表大会或全体职工讨论、协商，程序存在瑕疵，可作为抗辩点，但不必然导致解除违法。",
                    reasoning="第4条第2款要求民主程序；实践中程序瑕疵的后果需结合制度内容与公示情况判断。",
                    cites=["labor_contract@2008-01-01:第4条"],
                    depends=["rule_democratic"], risk="中",
                ))

            if proof == "只有口头指认":
                findings.append(Finding(
                    id="F_MISCONDUCT_PROOF", issue="违纪事实的举证",
                    conclusion="公司仅有口头指认，缺书面证据，举证不能的风险由用人单位承担。",
                    reasoning="因解除劳动合同发生的争议，用人单位负举证责任。",
                    cites=["labor_js1@2021-01-01:第44条", "labor_contract@2008-01-01:第39条"],
                    depends=["misconduct_proof"], risk="高",
                ))

            if union == "没有通知":
                illegal_flag = True
                findings.append(Finding(
                    id="F_UNION", issue="解除程序：通知工会",
                    conclusion="若公司已建立工会而解除前未通知，且未在起诉前补正，法院可支持违法解除赔偿金。",
                    reasoning="单方解除应事先将理由通知工会；未通知且未补正构成程序违法。该规则以用人单位已建立工会为前提。",
                    cites=["labor_contract@2008-01-01:第43条", "labor_js1@2021-01-01:第47条"],
                    depends=["union_notified"], risk="高",
                    assumptions=["以用人单位已建立工会组织为前提"],
                ))
            elif union == "公司没有工会":
                assumptions.append("公司未建立工会时，第43条的通知义务如何适用存在地区差异，需按当地裁审口径核实。")

            if illegal_flag:
                confidence = "较高"
            elif publicized == "有签收或公示" and proof in ("有书面证据", "有证人但无书面材料"):
                confidence = "解除可能合法，但需审查制度内容与违纪程度是否相当"

        # 4) 不胜任分支
        elif reason == "不胜任工作":
            training = facts.get("training_or_transfer")
            notice = facts.get("notice_30d")
            if training == "没有":
                illegal_flag = True
                findings.append(Finding(
                    id="F_INCOMPETENCE", issue="不胜任解除的前置条件",
                    conclusion="公司未培训也未调岗即解除，不符合第40条的实体条件，违法解除风险高。",
                    reasoning="不胜任工作须经培训或者调整工作岗位，仍不能胜任，才可提前三十日通知或支付代通知金后解除。",
                    cites=["labor_contract@2008-01-01:第40条"],
                    depends=["training_or_transfer"], risk="高",
                ))
            if notice == "都没有" and not illegal_flag:
                findings.append(Finding(
                    id="F_NOTICE", issue="代通知金",
                    conclusion="解除本身可能成立，但公司未提前三十日通知，应额外支付一个月工资（N+1）。",
                    reasoning="第40条要求提前三十日书面通知或额外支付一个月工资。",
                    cites=["labor_contract@2008-01-01:第40条"],
                    depends=["notice_30d"], risk="中",
                ))

        # 5) 其他/说不清
        else:
            gaps.append("解除理由尚不明确，需取得解除通知书或要求公司书面说明。")

    # 6) 赔偿计算
    illegal = illegal_flag
    if illegal:
        pay_type, extra_notice = "2N", False
    elif reason == "严重违纪":
        pay_type, extra_notice = "0", False
    elif who == "劳动者辞职":
        pay_type, extra_notice = "0", False
    else:
        pay_type = "N"
        extra_notice = (reason == "不胜任工作" and facts.get("notice_30d") == "都没有")
    comp = compute_compensation(facts, pay_type=pay_type, extra_notice=extra_notice)
    if comp.get("ok"):
        alt = compute_compensation(facts, pay_type="2N") if pay_type != "2N" else None
        extra = ""
        if alt and alt.get("ok"):
            extra = (f" 若后续认定构成违法解除，按 2N 计算约为 {alt['amount']:,.0f} 元。")
        findings.append(Finding(
            id="F_COMPENSATION",
            issue="赔偿金/经济补偿计算",
            conclusion=(f"按工作年限 {comp['work_years_label']}、基数 {comp['base']:,.0f} 元/月计算，"
                        f"{'违法解除赔偿金（2N）' if pay_type == '2N' else ('经济补偿（N）' if pay_type == 'N' else '经济补偿')}约为 "
                        f"{comp['amount']:,.0f} 元。计算公式：{comp['formula']}。" + extra),
            reasoning=comp["years_rule"],
            cites=comp["cites"],
            depends=["start_date", "dismiss_date", "monthly_wage"],
            risk="中" if pay_type != "0" else "低",
            assumptions=comp["assumptions"],
        ))
        assumptions.extend(comp["assumptions"])
    else:
        gaps.append("缺少计算赔偿所需的" + "、".join(comp.get("missing", [])) + "。")

    # 7) 救济路径
    claim = facts.get("claim_type")
    if claim == "要求继续履行":
        findings.append(Finding(
            id="F_REMEDY", issue="救济路径",
            conclusion="可以主张继续履行劳动合同；若劳动合同已不能继续履行，仲裁/法院可转而支持赔偿金。",
            reasoning="劳动者要求继续履行的，用人单位应当继续履行；不能继续履行的，按第87条支付赔偿金。",
            cites=["labor_contract@2008-01-01:第48条"],
            depends=["claim_type"], risk="中",
        ))
    elif claim == "要求赔偿金":
        findings.append(Finding(
            id="F_REMEDY", issue="救济路径",
            conclusion="选择赔偿金路径，则不再主张继续履行；赔偿金为经济补偿标准的二倍。",
            reasoning="第48条、第87条。",
            cites=["labor_contract@2008-01-01:第48条", "labor_contract@2008-01-01:第87条"],
            depends=["claim_type"], risk="低",
        ))

    headline = _dismissal_headline(illegal_flag, confidence, reason, comp, lim)
    return Analysis(
        case_type="labor_dismissal", as_of=facts.get("dismiss_date", ""),
        headline=headline, findings=findings, gaps=gaps,
        assumptions=list(dict.fromkeys(assumptions)),
        metadata={"illegal": illegal_flag, "confidence": confidence,
                  "limitation": lim, "compensation": comp, "reason": reason,
                  "state_revision": revision},
    )


def _dismissal_headline(illegal: bool, confidence: str, reason: str, comp: dict,
                        lim: dict | None = None) -> str:
    prefix = ""
    if lim and lim.get("ok") and lim.get("expired"):
        prefix = (f"【先看时效】按解除日 {lim['start']} 计算，仲裁时效已于 "
                  f"{lim['deadline']} 届满，对方可提时效抗辩；应先核查有无中断、中止事由。"
                  f"以下实体分析仅在时效问题能解决时才有实际意义。\n\n")
    if illegal:
        base = "现有事实更支持“违法解除”，可主张赔偿金（2N）或继续履行。"
        if comp.get("ok"):
            base += f"按现有数据估算赔偿金约 {comp['amount']:,.0f} 元。"
        return prefix + base
    if reason == "严重违纪":
        return prefix + "尚不足以认定违法解除：需要看规章制度是否有效公示、违纪事实是否有证据、解除是否通知工会。"
    if reason == "不胜任工作":
        return prefix + "解除是否符合第40条取决于是否培训/调岗、是否提前通知；不符合则可能构成违法解除。"
    return prefix + "解除理由尚不明确，暂不能给出确定性结论；建议先取得书面解除通知。"


# ------------------------------------------------------------------ 侵权
def _tort_interp_version(accident: str) -> tuple[str, str]:
    if accident >= "2022-05-01":
        return "tort_interp_2022", "2022-05-01"
    if accident >= "2021-01-01":
        return "tort_interp_2020", "2021-01-01"
    if accident >= "2004-05-01":
        return "tort_interp_2003", "2004-05-01"
    return "", ""


def _tort_cite(accident: str, kind: str) -> str:
    """Cite the statute that was in force for this accident date."""
    if accident and accident < "2021-01-01":
        return {
            "fault": "tort_liability_law@2010-07-01:第6条",
            "damages": "tort_liability_law@2010-07-01:第16条",
            "employer": "tort_liability_law@2010-07-01:第34条",
            "traffic": "tort_liability_law@2010-07-01:第48条",
        }[kind]
    return {
        "fault": "civil_code_tort@2021-01-01:第1165条",
        "damages": "civil_code_tort@2021-01-01:第1179条",
        "employer": "civil_code_tort@2021-01-01:第1191条",
        "traffic": "civil_code_tort@2021-01-01:第1213条",
    }[kind]


def assess_tort(facts: dict, today: str | None = None,
                revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    assumptions: list[str] = []
    accident = facts.get("accident_date", "")

    lim = check_limitation("tort_injury", accident, today)
    if lim.get("ok"):
        findings.append(Finding(
            id="T_LIMITATION", issue="诉讼时效",
            conclusion=(f"{lim['label']}，自 {lim['start']} 起算，届满日 {lim['deadline']}；"
                        + ("已超过时效，需核查中止、中断事由。" if lim["expired"]
                           else f"尚未届满（剩余约 {lim['days_left']} 天）。")),
            reasoning=lim["note"], cites=[lim["basis"]],
            depends=["accident_date"], risk="高" if lim["expired"] else "中",
            assumptions=["以事故发生日起算（简化假设）"],
        ))
        if lim["expired"]:
            gaps.append("诉讼时效可能已过，需核实是否存在中断、中止事由。")

    law_id, valid_from = _tort_interp_version(accident) if accident else ("", "")
    if law_id:
        version_name = law_id.split("_")[-1]
        if accident < "2021-01-01":
            findings.append(Finding(
                id="T_VERSION", issue="法律适用（时间效力）",
                conclusion=f"事故发生于 {accident}，民法典尚未施行，应适用《侵权责任法》与《人身损害赔偿解释（{version_name}）》（{valid_from} 起施行）。",
                reasoning="民法典施行前的法律事实原则上适用当时的法律、司法解释。",
                cites=["tort_liability_law@2010-07-01:第6条"],
                depends=["accident_date"], risk="低",
            ))
        else:
            findings.append(Finding(
                id="T_VERSION", issue="法律适用（时间效力）",
                conclusion=f"事故发生于 {accident}，应适用《人身损害赔偿解释（{version_name}）》（{valid_from} 起施行）的赔偿标准。",
                reasoning="侵权损害赔偿适用行为时有效的法律与司法解释；"
                          "民法典施行前的法律事实原则上适用当时的法律、司法解释。",
                cites=["civil_time_effect@2021-01-01:第1条"],
                depends=["accident_date"], risk="低",
            ))
        if accident >= "2022-05-01":
            findings.append(Finding(
                id="T_STANDARD", issue="残疾/死亡赔偿金标准",
                conclusion="2022-05-01 起残疾赔偿金、死亡赔偿金统一按城镇居民人均可支配收入计算，不再区分城乡；农村户籍受害人不再因户籍被压低标准。",
                reasoning="2022年修正删去了“农村居民人均纯收入”的表述。",
                cites=["tort_interp_2022@2022-05-01:第12条", "tort_interp_2022@2022-05-01:第15条"],
                depends=["accident_date"], risk="低",
            ))
        elif law_id == "tort_interp_2003":
            findings.append(Finding(
                id="T_STANDARD", issue="残疾/死亡赔偿金标准",
                conclusion="本案适用2003年司法解释，残疾/死亡赔偿金按城镇居民人均可支配收入或农村居民人均纯收入分别计算。",
                reasoning="2021-01-01 前适用2003年解释；2020年修正版自2021-01-01起施行。",
                cites=["tort_interp_2003@2004-05-01:第25条", "tort_interp_2003@2004-05-01:第29条"],
                depends=["accident_date"], risk="中",
            ))
        else:
            residence = facts.get("residence")
            if residence == "农村" or residence == "农村户籍但城镇居住满一年":
                findings.append(Finding(
                    id="T_STANDARD", issue="残疾/死亡赔偿金标准",
                    conclusion=("本案适用 2022 年修正前的解释，残疾/死亡赔偿金按城镇或农村标准区分；"
                                "农村户籍受害人若能证明在城镇连续居住、主要收入来源于城镇满一年，可按城镇标准主张。"),
                    reasoning="2022-05-01 前的司法解释区分城镇居民人均可支配收入与农村居民人均纯收入。",
                    cites=["tort_interp_2020@2021-01-01:第12条", "tort_interp_2020@2021-01-01:第15条"],
                    depends=["accident_date", "residence"], risk="中",
                ))
    elif accident:
        gaps.append("事故发生日期早于2004-05-01，超出当前语料覆盖范围，需另行核查当时的法律。")

    resp = facts.get("responsibility")
    if resp and resp != "尚未认定":
        findings.append(Finding(
            id="T_LIABILITY", issue="责任划分与赔偿比例",
            conclusion=f"事故责任认定为“{resp}”，赔偿通常先由保险赔付，不足部分按责任比例由侵权人承担；具体比例由法院酌定。",
            reasoning="机动车交通事故先由交强险赔付，不足部分按过错分担；商业三者险按合同赔付。",
            cites=["road_traffic@2004-05-01:第76条", _tort_cite(accident, "traffic")],
            depends=["responsibility"], risk="低",
        ))

    if facts.get("employment") == "执行工作任务":
        findings.append(Finding(
            id="T_EMPLOYER", issue="责任主体",
            conclusion="驾驶人系执行工作任务，用人单位应承担侵权责任；用人单位赔偿后可向有故意或重大过失的工作人员追偿。",
            reasoning="用人单位责任（替代责任）。",
            cites=[_tort_cite(accident, "employer")],
            depends=["employment"], risk="低",
        ))

    if facts.get("injury"):
        findings.append(Finding(
            id="T_DAMAGES", issue="可主张的赔偿项目",
            conclusion="可主张医疗费、护理费、交通费、营养费、住院伙食补助费、误工费；构成残疾的还可主张辅助器具费与残疾赔偿金，死亡的还包括丧葬费与死亡赔偿金。",
            reasoning="赔偿项目以实际损失与伤残情况为基础，需凭票据、病历、鉴定意见举证。",
            cites=[_tort_cite(accident, "damages")],
            depends=["injury"], risk="低",
        ))

    headline = "交通事故人身损害。"
    if law_id:
        ver = law_id.split("_")[-1]
        headline += f"事故发生于 {accident}，适用《人身损害赔偿解释（{ver}）》。"
        if accident >= "2022-05-01":
            headline += "赔偿标准已统一按城镇居民口径，不再区分城乡。"
        else:
            headline += "残疾/死亡赔偿金仍区分城乡标准，农村户籍受害人可举证按城镇标准主张。"
    headline += "具体赔偿金额需依据票据、误工证明和伤残鉴定意见计算。"
    if lim.get("ok") and lim.get("expired"):
        headline = (f"【先看时效】诉讼时效可能已于 {lim['deadline']} 届满，对方可提时效抗辩；"
                    f"应先核查有无中断、中止事由。\n\n") + headline
    return Analysis(
        case_type="tort_injury", as_of=accident, headline=headline,
        findings=findings, gaps=gaps, assumptions=list(dict.fromkeys(assumptions)),
        metadata={"interp": law_id, "limitation": lim, "state_revision": revision},
    )


def analyse(case_type: str, facts: dict, today: str | None = None,
            revision: int = 0) -> Analysis:
    if case_type == "labor_dismissal":
        return assess_dismissal(facts, today, revision)
    if case_type == "tort_injury":
        return assess_tort(facts, today, revision)
    raise ValueError(f"unknown case type: {case_type}")

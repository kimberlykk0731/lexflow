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

CLAIM_LABELS = {
    "labor_dismissal": "解除/辞退",
    "labor_wage": "工资/欠薪",
    "labor_overtime": "加班费",
    "labor_double_pay": "未签合同二倍工资",
    "labor_work_injury": "工伤",
    "labor_social_insurance": "社保/公积金",
    "labor_annual_leave": "年休假",
    "labor_noncompete": "竞业限制",
    "labor_maternity": "三期/生育",
    "labor_dispatch": "派遣/外包/新业态",
    "labor_contract": "合同/试用期",
    "labor_procedure": "仲裁/诉讼程序",
    "tort_injury": "交通事故人身损害",
}


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
    if e == anniversary:
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



# =====================================================================
# 劳动法计算器（deterministic, shared by several claim analysers）
# =====================================================================
HOURS_PER_MONTH = 21.75 * 8


def hourly_wage(monthly_wage: float) -> float:
    return float(monthly_wage) / HOURS_PER_MONTH


def calculate_overtime(monthly_wage: float, weekday_h: float = 0,
                       rest_h: float = 0, holiday_h: float = 0) -> dict:
    hourly = hourly_wage(monthly_wage)
    parts = {
        "weekday": round(hourly * 1.5 * (weekday_h or 0), 2),
        "rest": round(hourly * 2 * (rest_h or 0), 2),
        "holiday": round(hourly * 3 * (holiday_h or 0), 2),
    }
    total = round(sum(parts.values()), 2)
    return {
        "ok": True, "hourly": round(hourly, 2), "parts": parts, "amount": total,
        "formula": (f"小时工资 {hourly:,.2f} 元；工作日 {weekday_h:g}h×150% + "
                    f"休息日 {rest_h:g}h×200% + 法定节假日 {holiday_h:g}h×300%"),
        "hours": {"weekday": weekday_h or 0, "rest": rest_h or 0, "holiday": holiday_h or 0},
        "cites": ["labor_law@1995-01-01:第44条", "wage_payment@1995-01-01:第13条"],
        "assumptions": ["月计薪天数按 21.75 天、每天 8 小时折算。",
                        "加班费基数是否包含奖金、补贴存在地区差异，需按当地口径核对。"],
    }


def calculate_double_wage(monthly_wage: float, months: float) -> dict:
    months = max(0.0, min(float(months or 0), 11.0))
    amount = round(float(monthly_wage) * months, 2)
    return {
        "ok": True, "months": months, "amount": amount,
        "formula": f"{monthly_wage:,.0f} 元/月 × {months:g} 个月（上限 11 个月）",
        "cites": ["labor_contract@2008-01-01:第82条", "labor_js2@2025-09-01:第6条"],
        "assumptions": ["二倍工资差额按劳动者应得工资计算，最多 11 个月。",
                        "若劳动者本人故意或重大过失不签，可能不支持（解释二第7条）。"],
    }


def calculate_annual_leave(monthly_wage: float, unused_days: float) -> dict:
    daily = float(monthly_wage) / 21.75
    extra = round(daily * unused_days * 2, 2)
    total = round(daily * unused_days * 3, 2)
    return {
        "ok": True, "daily": round(daily, 2), "unused_days": unused_days,
        "amount": extra, "total_300": total,
        "formula": f"日工资 {daily:,.2f} 元 × {unused_days:g} 天 × 200%（额外补偿；300% 中含正常工资）",
        "cites": ["annual_leave@2008-01-01:第3条", "annual_leave@2008-01-01:第5条"],
        "assumptions": ["日工资按月工资 ÷ 21.75 折算；未休年假工资中 100% 已随正常工资发放，"
                        "可另行主张的是 200%。"],
    }


def calculate_noncompete(monthly_wage: float, months: float,
                         agreed_monthly: float | None = None) -> dict:
    months = max(0.0, min(float(months or 0), 24.0))
    base = agreed_monthly if agreed_monthly else float(monthly_wage) * 0.3
    return {
        "ok": True, "monthly": round(float(base), 2), "months": months,
        "amount": round(float(base) * months, 2),
        "formula": (f"{float(base):,.2f} 元/月 × {months:g} 个月"
                    + ("（约定标准）" if agreed_monthly else "（按离职前月平均工资的 30%）")),
        "cites": ["labor_contract@2008-01-01:第23条", "labor_js1@2021-01-01:第36条"],
        "assumptions": ["未约定补偿时按离职前十二个月平均工资的 30% 计算；"
                        "低于当地最低工资标准的，按最低工资标准支付。"],
    }


INJURY_SUBSIDY_MONTHS = {1: 27, 2: 25, 3: 23, 4: 21, 5: 18, 6: 16,
                         7: 13, 8: 11, 9: 9, 10: 7}


def calculate_work_injury(monthly_wage: float, level: int | None) -> dict:
    if level not in INJURY_SUBSIDY_MONTHS:
        return {"ok": False, "reason": "缺少伤残等级（1-10级）"}
    months = INJURY_SUBSIDY_MONTHS[level]
    return {
        "ok": True, "level": level, "months": months,
        "amount": round(float(monthly_wage) * months, 2),
        "formula": f"{monthly_wage:,.0f} 元/月 × {months} 个月（一次性伤残补助金）",
        "cites": ["work_injury_reg@2011-01-01:第35条", "work_injury_reg@2011-01-01:第37条"],
        "assumptions": ["一次性伤残补助金按本人工资（受伤前 12 个月平均缴费工资）计算。",
                        "5-6 级的一次性工伤医疗补助金/伤残就业补助金、"
                        "7-10 级的一次性医疗/就业补助金按地方标准另算，未纳入。"],
    }


# =====================================================================
# 各请求权的分析器
# =====================================================================
def _limitation_finding(anchor: str, today: str | None, claim_id: str,
                        notes: str = "") -> tuple[Finding | None, dict, str]:
    lim = check_limitation("labor_dismissal", anchor, today)
    if not lim.get("ok"):
        return None, lim, "缺少可解析的日期，无法判断仲裁时效。"
    f = Finding(
        id=f"F_LIMITATION_{claim_id.upper()}", issue="仲裁时效",
        conclusion=(f"{lim['label']}，自 {lim['start']} 起算，届满日 {lim['deadline']}；"
                    + ("已超过一年，对方很可能提出时效抗辩；需核查中断、中止事由。"
                       if lim["expired"] else f"目前尚未届满（剩余约 {lim['days_left']} 天）。")),
        reasoning=lim["note"] + (" " + notes if notes else ""),
        cites=[lim["basis"]], depends=["dismiss_date"],
        risk="高" if lim["expired"] else "中",
        assumptions=["以解除/离职日为时效起算点；实际可能以知道权利被侵害之日为准。"],
    )
    gap = ("时效可能已过：需核实是否存在向单位主张、投诉、调解等中断事由。"
           if lim["expired"] else "")
    return f, lim, gap


def assess_wage(facts: dict, today: str | None = None, revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    assumptions: list[str] = []
    owed = facts.get("wage_owed")
    base = facts.get("monthly_wage")
    days = facts.get("wage_period") or "未说明"
    if isinstance(owed, (int, float)) and owed > 0:
        findings.append(Finding(
            id="F_WAGE_AMOUNT", issue="欠付工资数额",
            conclusion=f"当事人主张欠付工资 {owed:,.0f} 元，期间为 {days}。",
            reasoning="工资应当以货币形式按月足额支付；解除或终止时应当一次付清。",
            cites=["labor_law@1995-01-01:第50条", "wage_payment@1995-01-01:第9条"],
            depends=["wage_owed", "wage_period"], risk="中",
        ))
    else:
        gaps.append("欠薪金额和期间尚未明确，无法计算请求数额。")
    if facts.get("reduced_salary") == "被降薪":
        findings.append(Finding(
            id="F_WAGE_REDUCTION", issue="单方降薪",
            conclusion="用人单位单方降低工资，未经协商一致的，劳动者可主张补足差额。",
            reasoning="变更劳动合同约定的内容应当协商一致并采用书面形式。",
            cites=["labor_contract@2008-01-01:第35条", "labor_contract@2008-01-01:第30条"],
            depends=["reduced_salary"], risk="中",
        ))
    if facts.get("wage_reason") == "无故拖欠":
        findings.append(Finding(
            id="F_WAGE_PENALTY", issue="加付赔偿金",
            conclusion="无故拖欠工资的，经劳动行政部门责令限期支付仍不支付的，"
                       "可要求按应付金额 50%-100% 加付赔偿金。",
            reasoning="加付赔偿金以劳动行政部门责令支付为前提，仲裁中直接主张可能不被支持。",
            cites=["labor_contract@2008-01-01:第85条"], depends=["wage_reason"], risk="中",
        ))
    anchor = facts.get("dismiss_date") or ""
    note = ("劳动关系存续期间因拖欠劳动报酬发生争议，不受一年时效限制；"
            "劳动关系终止的，应当自终止之日起一年内提出。")
    f, lim, gap = _limitation_finding(anchor, today, "wage", note)
    if f:
        findings.append(f)
    if gap:
        gaps.append(gap)
    elif not anchor:
        gaps.append("缺少离职日期；若劳动关系仍存续，欠薪仲裁不受一年时效限制。")
    findings.append(Finding(
        id="F_WAGE_EVIDENCE", issue="举证与证据",
        conclusion="劳动者需先证明工资标准和欠付事实；工资支付凭证由用人单位保存的，"
                   "可要求单位提供，单位不提供承担不利后果。",
        reasoning="工资条、银行流水、微信转账、考勤记录可以形成初步证据链。",
        cites=["labor_dispute@2008-05-01:第6条", "labor_js1@2021-01-01:第44条"],
        depends=["wage_evidence"], risk="中",
    ))
    headline = ("欠薪案件先固定工资标准和欠付期间；离职时公司应一次付清。"
                + (f" 目前主张 {owed:,.0f} 元。" if isinstance(owed, (int, float)) else ""))
    if f and lim.get("expired"):
        headline = f"【先看时效】仲裁时效可能已于 {lim['deadline']} 届满。\n\n" + headline
    return Analysis(case_type="labor_wage", as_of=anchor or "", headline=headline,
                    findings=findings, gaps=gaps, assumptions=assumptions,
                    metadata={"limitation": lim, "state_revision": revision})


def assess_overtime(facts: dict, today: str | None = None, revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    assumptions: list[str] = []
    exists = facts.get("overtime_exists")
    if exists == "没有":
        return Analysis(case_type="labor_overtime", as_of="", headline="当事人表示没有加班，暂不产生加班费请求。", findings=[Finding(
            id="F_OT_NONE", issue="加班事实", conclusion="当事人表示没有加班，暂不产生加班费请求。",
            reasoning="没有加班事实，无需进入加班费计算。", cites=[], risk="低")],
            gaps=[], assumptions=[], metadata={"state_revision": revision})
    if exists != "有":
        gaps.append("尚未确认是否存在加班；若没有加班，本请求不成立。")
    wd = facts.get("overtime_hours_weekday") or 0
    rest = facts.get("overtime_hours_rest") or 0
    hol = facts.get("overtime_hours_holiday") or 0
    wage = facts.get("monthly_wage")
    calc = None
    if isinstance(wage, (int, float)) and wage > 0 and (wd or rest or hol):
        calc = calculate_overtime(wage, wd, rest, hol)
        findings.append(Finding(
            id="F_OT_AMOUNT", issue="加班费计算",
            conclusion=f"按目前提供的时长估算，加班费约为 {calc['amount']:,.0f} 元/月。",
            reasoning=calc["formula"],
            cites=calc["cites"], depends=["overtime_hours_weekday", "overtime_hours_rest",
                                          "overtime_hours_holiday", "monthly_wage"],
            risk="中", assumptions=calc["assumptions"]))
        assumptions.extend(calc["assumptions"])
    else:
        gaps.append("缺少月工资或各类加班时长，无法计算加班费。")
    schedule = facts.get("work_schedule")
    if schedule == "标准工时" or not schedule:
        findings.append(Finding(
            id="F_OT_SCHEDULE", issue="工时制度",
            conclusion="按标准工时处理：每日 8 小时、每周 40 小时，超出部分原则上属于加班。",
            reasoning="综合计算工时、不定时工时需经劳动行政部门审批；未经审批或未告知的，"
                      "一般仍按标准工时认定。",
            cites=["labor_law@1995-01-01:第36条", "labor_law@1995-01-01:第39条"],
            depends=["work_schedule"], risk="中"))
    elif schedule in ("综合计算工时", "不定时工时"):
        findings.append(Finding(
            id="F_OT_SCHEDULE", issue="特殊工时",
            conclusion=f"当事人执行{schedule}，需核查是否经审批、是否在合同中明确告知；"
                       "未经审批的，可能仍按标准工时计算加班费。",
            reasoning="特殊工时不是单位单方说了算，审批和告知缺一不可。",
            cites=["labor_law@1995-01-01:第39条"], depends=["work_schedule"], risk="高"))
    findings.append(Finding(
        id="F_OT_EVIDENCE", issue="加班举证",
        conclusion="劳动者先就加班事实存在承担初步举证责任；有证据证明考勤由单位掌握的，"
                   "可要求单位提供，单位不提供承担不利后果。",
        reasoning="考勤打卡、排班表、工作群消息、加班审批单是常见证据。",
        cites=["labor_js1@2021-01-01:第42条"], depends=["overtime_evidence"], risk="中"))
    if facts.get("overtime_paid") == "没有支付":
        gaps.append("公司未支付加班费；需核对是否存在调休、工资中是否已包含加班费。")
    anchor = facts.get("dismiss_date") or ""
    f, lim, gap = _limitation_finding(anchor, today, "overtime")
    if f:
        findings.append(f)
    if gap:
        gaps.append(gap)
    headline = "加班费按工作日 150%、休息日 200%、法定节假日 300% 计算。"
    if calc:
        headline += f" 按目前时长估算约 {calc['amount']:,.0f} 元/月。"
    else:
        headline += " 还需补充月工资和各类加班时长才能算金额。"
    return Analysis(case_type="labor_overtime", as_of=anchor, headline=headline,
                    findings=findings, gaps=gaps,
                    assumptions=list(dict.fromkeys(assumptions)),
                    metadata={"calculation": calc, "limitation": lim,
                              "state_revision": revision})


def assess_double_pay(facts: dict, today: str | None = None, revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    signed = facts.get("contract_signed")
    if signed in ("已签书面合同", "签了但没给我"):
        return Analysis(case_type="labor_double_pay", as_of="", headline="已签订书面劳动合同，需区分未订立与未交付文本。", findings=[Finding(
            id="F_DP_NONE", issue="书面合同",
            conclusion="已签订书面劳动合同，原则上不支持未签合同二倍工资；"
                       "但未将文本交付劳动者的，可另行主张。",
            reasoning="二倍工资针对的是未订立书面合同，而不是未交付合同文本。",
            cites=["labor_contract@2008-01-01:第82条"], risk="低")],
            gaps=[], assumptions=[], metadata={"state_revision": revision})
    months = facts.get("no_contract_months")
    wage = facts.get("monthly_wage")
    calc = None
    if isinstance(months, (int, float)) and isinstance(wage, (int, float)) and wage > 0:
        calc = calculate_double_wage(wage, months)
        findings.append(Finding(
            id="F_DP_AMOUNT", issue="二倍工资差额",
            conclusion=f"按 {calc['months']:g} 个月估算，二倍工资差额约为 {calc['amount']:,.0f} 元。",
            reasoning=calc["formula"],
            cites=calc["cites"], depends=["no_contract_months", "monthly_wage"],
            risk="中", assumptions=calc["assumptions"]))
    else:
        gaps.append("未签合同的起止时间或月工资不明，无法计算二倍工资。")
    findings.append(Finding(
        id="F_DP_RULE", issue="计算规则",
        conclusion="自用工之日起满一个月的次日至满一年的前一日，最多支持 11 个月；"
                   "解释二明确按月计算，不满一个月按实际工作日计算。",
        reasoning="二倍工资是对用人单位不签书面合同的惩罚，不是劳动报酬。",
        cites=["labor_contract@2008-01-01:第82条", "labor_js2@2025-09-01:第6条"],
        risk="中"))
    findings.append(Finding(
        id="F_DP_DEFENSE", issue="用人单位抗辩",
        conclusion="若单位能证明因不可抗力、劳动者本人故意或重大过失未签，可能不支持二倍工资；"
                   "空白合同、代签合同不等于有效订立。",
        reasoning="解释二第7条列举了免责情形；实践中单位常以“劳动者拒签”抗辩，需要证据。",
        cites=["labor_js2@2025-09-01:第7条"], risk="高"))
    anchor = facts.get("dismiss_date") or ""
    f, lim, gap = _limitation_finding(
        anchor, today, "doublepay",
        "二倍工资差额的时效存在按月计算与整体计算两种实践，需按当地口径核对。")
    if f:
        findings.append(f)
    if gap:
        gaps.append(gap)
    headline = "未签书面合同可主张最多 11 个月的二倍工资差额。"
    if calc:
        headline += f" 按目前信息估算约 {calc['amount']:,.0f} 元。"
    return Analysis(case_type="labor_double_pay", as_of=anchor, headline=headline,
                    findings=findings, gaps=gaps, assumptions=[],
                    metadata={"calculation": calc, "limitation": lim,
                              "state_revision": revision})


def assess_work_injury(facts: dict, today: str | None = None, revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    assumptions: list[str] = []
    at_work = facts.get("injury_at_work")
    if at_work == "不属于工伤":
        return Analysis(case_type="labor_work_injury", as_of="", headline="目前描述不属于工伤，认定及救济路径需另行核实。", findings=[Finding(
            id="F_WI_NONE", issue="工伤认定",
            conclusion="目前事实更像不属于工伤；若对认定不服，可在法定期限内申请行政复议或诉讼。",
            reasoning="工伤认定以工作原因、工作场所、工作时间为核心。", cites=[], risk="中")],
            gaps=[], assumptions=[], metadata={"state_revision": revision})
    if at_work:
        basis = ("work_injury_reg@2011-01-01:第15条" if at_work == "视同工伤情形"
                 else "work_injury_reg@2011-01-01:第14条")
        findings.append(Finding(
            id="F_WI_SCOPE", issue="是否属于工伤",
            conclusion=f"按当事人描述（{at_work}），可能落入应当认定/视同工伤的情形，"
                       "最终以社会保险行政部门的认定为准。",
            reasoning="上下班途中交通事故还需满足“非本人主要责任”等条件。",
            cites=[basis], depends=["injury_at_work"], risk="中"))
    else:
        gaps.append("受伤情形不明，无法判断是否属于工伤。")
    reported = facts.get("injury_reported")
    if reported == "还没申请":
        gaps.append("尚未申请工伤认定：单位应在 30 日内申请，单位不申请的，"
                    "个人应在事故伤害发生之日起 1 年内申请。")
    findings.append(Finding(
        id="F_WI_PROCEDURE", issue="工伤认定程序",
        conclusion="单位应在事故伤害发生之日起 30 日内申请；单位未申请的，"
                   "劳动者可在 1 年内自行申请。单位未在 30 日内申请的，"
                   "期间发生的工伤待遇由单位负担。",
        reasoning="工伤认定是享受工伤保险待遇的前提；认定后还需做劳动能力鉴定。",
        cites=["work_injury_reg@2011-01-01:第17条"],
        depends=["injury_reported", "injury_recognized"], risk="高"))
    level = facts.get("disability_level")
    wage = facts.get("monthly_wage")
    calc = None
    if isinstance(level, str) and level.endswith("级"):
        try:
            lv = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
                  "七": 7, "八": 8, "九": 9, "十": 10}[level[0]]
        except KeyError:
            lv = None
        if lv and isinstance(wage, (int, float)) and wage > 0:
            calc = calculate_work_injury(wage, lv)
            findings.append(Finding(
                id="F_WI_AMOUNT", issue="一次性伤残补助金",
                conclusion=f"{level}伤残的一次性伤残补助金约为 {calc['amount']:,.0f} 元"
                           f"（{calc['months']} 个月本人工资）。",
                reasoning=calc["formula"], cites=calc["cites"],
                depends=["disability_level", "monthly_wage"], risk="中",
                assumptions=calc["assumptions"]))
            assumptions.extend(calc["assumptions"])
        else:
            gaps.append("伤残等级或本人工资不明，无法估算一次性伤残补助金。")
    else:
        gaps.append("尚未做劳动能力鉴定/伤残等级不明，伤残待遇无法计算。")
    if facts.get("work_injury_insurance") == "没有参加":
        findings.append(Finding(
            id="F_WI_UNINSURED", issue="未参保责任",
            conclusion="单位未参加工伤保险的，工伤保险待遇由用人单位支付。",
            reasoning="未参保不能成为单位免责的理由。",
            cites=["work_injury_reg@2011-01-01:第62条",
                   "social_insurance@2011-07-01:第41条"],
            depends=["work_injury_insurance"], risk="高"))
    headline = "工伤案件按“认定 → 劳动能力鉴定 → 待遇计算”三步走。"
    if calc:
        headline += f" 按{level}伤残估算一次性伤残补助金约 {calc['amount']:,.0f} 元。"
    return Analysis(case_type="labor_work_injury", as_of=facts.get("injury_date", ""),
                    headline=headline, findings=findings, gaps=gaps,
                    assumptions=list(dict.fromkeys(assumptions)),
                    metadata={"calculation": calc, "state_revision": revision})


def assess_social_insurance(facts: dict, today: str | None = None,
                            revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    status = facts.get("social_insurance")
    if status in ("未缴纳", "断缴"):
        findings.append(Finding(
            id="F_SI_STATUS", issue="未缴/断缴社保",
            conclusion="用人单位未依法缴纳社会保险费。补缴一般向社保费征收机构投诉；"
                       "因此被迫解除的，可主张经济补偿。",
            reasoning="社保征缴属于行政征收，不属于劳动仲裁受理范围；"
                      "但“被迫解除+经济补偿”属于劳动争议。",
            cites=["social_insurance@2011-07-01:第58条", "social_insurance@2011-07-01:第63条",
                   "labor_contract@2008-01-01:第38条", "labor_js2@2025-09-01:第19条"],
            depends=["social_insurance"], risk="中"))
    elif status == "按最低基数缴纳":
        findings.append(Finding(
            id="F_SI_BASE", issue="缴费基数不足",
            conclusion="按最低基数而非实际工资缴纳，可能影响养老、医疗、生育、工伤待遇；"
                       "可向社保征收机构投诉要求补足，并就实际损失主张赔偿。",
            reasoning="缴费基数不实造成的待遇差额，实践中赔偿路径存在地区差异。",
            cites=["social_insurance@2011-07-01:第60条"], depends=["social_insurance"], risk="中"))
    else:
        gaps.append("社保缴纳情况尚未确认。")
    if facts.get("social_insurance_claim") == "要求被迫解除经济补偿":
        findings.append(Finding(
            id="F_SI_FORCED", issue="被迫解除经济补偿",
            conclusion="以单位未依法缴纳社保为由解除劳动合同的，可主张经济补偿（N）。",
            reasoning="“自愿放弃社保”的约定或承诺无效，不影响劳动者据此解除并主张补偿。",
            cites=["labor_contract@2008-01-01:第38条", "labor_contract@2008-01-01:第46条",
                   "labor_js2@2025-09-01:第19条"], risk="中"))
    if facts.get("housing_fund") == "未缴纳":
        findings.append(Finding(
            id="F_SI_FUND", issue="住房公积金",
            conclusion="公积金不属于劳动仲裁受案范围，通常向住房公积金管理中心投诉。",
            reasoning="征缴路径与社保类似，走行政投诉而非仲裁。", cites=[], risk="低"))
    headline = "社保问题先分清两条路：补缴找社保征收机构，被迫解除/损失赔偿走劳动仲裁。"
    if status in ("未缴纳", "断缴"):
        headline += " 你描述的情况可能同时支持这两条路。"
    return Analysis(case_type="labor_social_insurance", as_of="", headline=headline,
                    findings=findings, gaps=gaps, assumptions=[],
                    metadata={"state_revision": revision})


def assess_annual_leave(facts: dict, today: str | None = None,
                        revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    years = facts.get("cumulative_work_years")
    entitled = None
    if isinstance(years, (int, float)):
        entitled = 5 if years < 10 else (10 if years < 20 else 15)
    taken = facts.get("annual_leave_taken")
    wage = facts.get("monthly_wage")
    calc = None
    if entitled is not None and isinstance(taken, (int, float)) and isinstance(wage, (int, float)):
        unused = max(0.0, entitled - taken)
        if unused > 0:
            calc = calculate_annual_leave(wage, unused)
            findings.append(Finding(
                id="F_AL_AMOUNT", issue="未休年假工资",
                conclusion=f"按累计工作 {years:g} 年、应休 {entitled} 天、已休 {taken:g} 天计算，"
                           f"未休 {unused:g} 天，可另主张约 {calc['amount']:,.0f} 元。",
                reasoning=calc["formula"], cites=calc["cites"],
                depends=["cumulative_work_years", "annual_leave_taken", "monthly_wage"],
                risk="中", assumptions=calc["assumptions"]))
    else:
        gaps.append("累计工作年限、已休天数或月工资不明，无法计算未休年假工资。")
    findings.append(Finding(
        id="F_AL_RULE", issue="年假天数与折算",
        conclusion="累计工作满 1 年不满 10 年 5 天，满 10 年不满 20 年 10 天，满 20 年 15 天；"
                   "未休年假按日工资 300% 支付（其中 200% 为额外补偿）。",
        reasoning="年假一般不跨年度安排；离职时按当年度已过日历天数折算。",
        cites=["annual_leave@2008-01-01:第3条", "annual_leave@2008-01-01:第5条"], risk="中"))
    findings.append(Finding(
        id="F_AL_LIMITATION", issue="年假时效",
        conclusion="未休年假工资不属于劳动报酬，很多地区按年度分别起算一年仲裁时效；"
                   "陈年未休年假很容易被时效抗辩。",
        reasoning="与欠薪不同，年假工资不适用“劳动关系存续期间不受一年限制”的规则。",
        cites=["labor_dispute@2008-05-01:第27条"], risk="高"))
    headline = "未休年假可主张 200% 额外补偿（300% 中含正常工资），但时效按年度计算，越早主张越好。"
    if calc:
        headline += f" 按目前信息估算约 {calc['amount']:,.0f} 元。"
    return Analysis(case_type="labor_annual_leave", as_of="", headline=headline,
                    findings=findings, gaps=gaps, assumptions=[],
                    metadata={"calculation": calc, "entitled": entitled,
                              "state_revision": revision})


def assess_noncompete(facts: dict, today: str | None = None,
                      revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    signed = facts.get("noncompete_signed")
    if signed == "没有签":
        return Analysis(case_type="labor_noncompete", as_of="", headline="没有签订竞业限制协议，原则上不受竞业限制约束。", findings=[Finding(
            id="F_NC_NONE", issue="竞业限制协议",
            conclusion="没有签订竞业限制协议，原则上不受竞业限制约束。",
            reasoning="竞业限制以书面约定为前提。", cites=[], risk="低")],
            gaps=[], assumptions=[], metadata={"state_revision": revision})
    findings.append(Finding(
        id="F_NC_SCOPE", issue="协议是否有效",
        conclusion="竞业限制只适用于高级管理人员、高级技术人员和其他负有保密义务的人员；"
                   "没有接触商业秘密的，条款可能不生效。",
        reasoning="解释二第13条要求竞业限制的范围、地域、期限与劳动者实际接触的商业秘密相适应。",
        cites=["labor_contract@2008-01-01:第24条", "labor_js2@2025-09-01:第13条"],
        depends=["noncompete_signed"], risk="高"))
    months = facts.get("noncompete_months")
    if isinstance(months, (int, float)) and months > 24:
        gaps.append("约定竞业限制期限超过二年，超过部分无效。")
    wage = facts.get("monthly_wage")
    agreed = facts.get("noncompete_compensation")
    calc = None
    if (isinstance(months, (int, float)) and months > 0
            and ((isinstance(wage, (int, float)) and wage > 0)
                 or (isinstance(agreed, (int, float)) and agreed > 0))):
        calc = calculate_noncompete(wage if isinstance(wage, (int, float)) else 0, months,
                                    agreed if isinstance(agreed, (int, float)) else None)
        findings.append(Finding(
            id="F_NC_COMP", issue="竞业限制补偿",
            conclusion=f"按目前约定/法定标准估算，补偿约为 {calc['monthly']:,.0f} 元/月，"
                       f"合计约 {calc['amount']:,.0f} 元。",
            reasoning=calc["formula"], cites=calc["cites"],
            depends=["noncompete_months", "monthly_wage", "noncompete_compensation"],
            risk="中", assumptions=calc["assumptions"]))
    else:
        gaps.append("竞业限制期限或补偿标准不明，无法计算补偿。")
    if facts.get("noncompete_paid") == "没有支付":
        gaps.append("单位三个月未支付竞业限制补偿的，劳动者可请求解除竞业限制约定。")
        findings.append(Finding(
            id="F_NC_TERMINATE", issue="解除竞业限制",
            conclusion="因用人单位原因三个月未支付经济补偿的，劳动者可以请求解除竞业限制约定。",
            reasoning="单位不付补偿却要求劳动者遵守竞业限制，显失公平。",
            cites=["labor_js1@2021-01-01:第38条"], depends=["noncompete_paid"], risk="中"))
    if facts.get("new_employer_competitor") == "去了竞争单位":
        findings.append(Finding(
            id="F_NC_BREACH", issue="违约金风险",
            conclusion="若协议有效且劳动者违反，单位可要求返还已付补偿并支付违约金；"
                       "违约金过高时可请求调整。",
            reasoning="解释二第15条支持返还补偿+违约金，但违约金应与实际损失相当。",
            cites=["labor_contract@2008-01-01:第23条", "labor_js2@2025-09-01:第15条"],
            depends=["new_employer_competitor"], risk="高"))
    headline = "竞业限制先看人员范围、商业秘密和期限，再看补偿与违约金。"
    if calc:
        headline += f" 按目前信息估算补偿约 {calc['amount']:,.0f} 元。"
    return Analysis(case_type="labor_noncompete", as_of=facts.get("dismiss_date", ""),
                    headline=headline, findings=findings, gaps=gaps, assumptions=[],
                    metadata={"calculation": calc, "state_revision": revision})


def assess_maternity(facts: dict, today: str | None = None,
                     revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    status = facts.get("pregnancy_status")
    if status in ("孕期", "产期", "哺乳期"):
        findings.append(Finding(
            id="F_MT_PROTECT", issue="三期保护",
            conclusion=f"当事人处于{status}，用人单位不得因怀孕、生育、哺乳降低工资、"
                       "予以辞退或解除合同。",
            reasoning="三期女职工受特别保护；违法解除可主张 2N 或继续履行。",
            cites=["labor_contract@2008-01-01:第42条", "female_protection@2012-04-28:第5条"],
            depends=["pregnancy_status"], risk="高"))
    else:
        gaps.append("尚未确认是否处于孕期、产期或哺乳期。")
    if facts.get("maternity_dismissal") == "因怀孕/生育被辞退":
        findings.append(Finding(
            id="F_MT_DISMISS", issue="三期被辞退",
            conclusion="因怀孕/生育被辞退，原则上属于违法解除；可要求继续履行或 2N 赔偿金。",
            reasoning="单位需证明解除与怀孕无关，且符合法定事由和程序。",
            cites=["labor_contract@2008-01-01:第42条", "labor_contract@2008-01-01:第87条",
                   "female_protection@2012-04-28:第5条"], risk="高"))
    findings.append(Finding(
        id="F_MT_ALLOWANCE", issue="生育津贴/产假工资",
        conclusion="已参加生育保险的，生育津贴由基金按单位上年度职工月平均工资支付；"
                   "未参加的，由单位按产假前工资支付。津贴低于本人工资的，差额由单位补足。",
        reasoning="产假 98 天（难产/多胞胎另加），各地还有奖励假。",
        cites=["female_protection@2012-04-28:第7条", "female_protection@2012-04-28:第8条",
               "social_insurance@2011-07-01:第56条"], risk="中"))
    headline = "三期女职工被辞退、降薪或产假待遇被压低，都有专门保护规则。"
    return Analysis(case_type="labor_maternity", as_of=facts.get("dismiss_date", ""),
                    headline=headline, findings=findings, gaps=gaps, assumptions=[],
                    metadata={"state_revision": revision})


def assess_dispatch(facts: dict, today: str | None = None,
                    revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    form = facts.get("dispatch_type")
    findings.append(Finding(
        id="F_DP_FORM", issue="用工形式与责任主体",
        conclusion=(f"当事人描述为{form}。" if form else "用工形式尚未确认。")
                   + "派遣/外包/平台用工不只看合同名称，要看谁管理、谁发工资、谁承担用工责任。",
        reasoning="关联公司混同用工的，劳动者可以请求确认其中一个单位承担用工责任，"
                  "并可要求关联单位承担连带责任。",
        cites=["labor_contract@2008-01-01:第58条", "labor_js2@2025-09-01:第1条"],
        depends=["dispatch_type"], risk="中"))
    findings.append(Finding(
        id="F_DP_CONTROL", issue="劳动关系认定",
        conclusion="判断劳动关系看人格从属性、经济从属性和组织从属性："
                   "是否打卡/派单/考核、是否按月发工资、是否穿工服使用单位工具。",
        reasoning="新业态用工不能仅凭“合作协议”“个体户”排除劳动关系；"
                  "支配性劳动管理是核心。",
        cites=["labor_js2@2025-09-01:第1条"], depends=["work_management", "pay_by"],
        risk="高"))
    if facts.get("platform_worker") in ("外卖骑手", "网约车司机", "网络主播"):
        gaps.append("平台用工的劳动关系认定差异很大；需结合派单规则、考核、"
                    "收入分配和是否可自由拒绝订单综合判断。")
    findings.append(Finding(
        id="F_DP_DISPATCH", issue="劳务派遣限制",
        conclusion="劳务派遣只能在临时性、辅助性、替代性岗位使用；"
                   "用工单位给被派遣劳动者造成损害的，派遣单位与用工单位承担连带责任。",
        reasoning="派遣不是规避用工责任的工具；超范围派遣可能被认定与用工单位存在劳动关系。",
        cites=["labor_contract@2008-01-01:第66条", "labor_contract@2008-01-01:第92条"],
        depends=["dispatch_type"], risk="中"))
    headline = "派遣/外包/平台用工先看“谁在管理、谁发工资、谁担责”，再谈工伤、社保和欠薪。"
    return Analysis(case_type="labor_dispatch", as_of="", headline=headline,
                    findings=findings, gaps=gaps, assumptions=[],
                    metadata={"state_revision": revision})


def assess_contract(facts: dict, today: str | None = None,
                    revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    if facts.get("probation") == "有试用期":
        length = facts.get("probation_length")
        limit = "六个月（三年以上/无固定期限）、二个月（一年以上不满三年）、一个月（三个月以上不满一年）"
        findings.append(Finding(
            id="F_CT_PROBATION", issue="试用期长度",
            conclusion=f"约定试用期 {length:g} 个月。" if isinstance(length, (int, float))
                       else "已约定试用期，需核对长度。",
            reasoning=f"法定上限：{limit}；同一单位与同一劳动者只能约定一次试用期。",
            cites=["labor_contract@2008-01-01:第19条"], depends=["probation_length"], risk="中"))
    if facts.get("probation_wage") and facts.get("monthly_wage"):
        pw, mw = facts["probation_wage"], facts["monthly_wage"]
        if isinstance(pw, (int, float)) and isinstance(mw, (int, float)) and pw < mw * 0.8:
            findings.append(Finding(
                id="F_CT_PROBATION_PAY", issue="试用期工资",
                conclusion=f"试用期工资 {pw:,.0f} 元低于约定工资的 80%（{mw*0.8:,.0f} 元），"
                           "可能违法。",
                reasoning="试用期工资不得低于本单位相同岗位最低档工资或约定工资的 80%，"
                          "并不得低于当地最低工资标准。",
                cites=["labor_contract@2008-01-01:第20条"], risk="中"))
    if facts.get("illegal_probation") and facts.get("illegal_probation") != "没有":
        findings.append(Finding(
            id="F_CT_ILLEGAL", issue="违法约定试用期",
            conclusion="违法约定试用期且已履行的，按超过法定试用期的期间支付赔偿金。",
            reasoning="赔偿金标准为试用期满月工资，按已履行的超过法定试用期的期间计算。",
            cites=["labor_contract@2008-01-01:第83条"], depends=["illegal_probation"], risk="中"))
    if facts.get("contract_copies") == "没有给我":
        findings.append(Finding(
            id="F_CT_COPY", issue="合同文本交付",
            conclusion="用人单位未将劳动合同文本交付劳动者的，由劳动行政部门责令改正；"
                       "给劳动者造成损害的，应当赔偿。",
            reasoning="合同文本应由用人单位和劳动者各执一份。",
            cites=["labor_contract@2008-01-01:第16条", "labor_contract@2008-01-01:第81条"],
            depends=["contract_copies"], risk="低"))
    if facts.get("contract_terms_changed") == "被单方变更":
        findings.append(Finding(
            id="F_CT_CHANGE", issue="单方调岗降薪",
            conclusion="单方调岗降薪未经协商一致的，劳动者可拒绝；已实际履行的可主张补足差额。",
            reasoning="变更劳动合同应当协商一致并采用书面形式。",
            cites=["labor_contract@2008-01-01:第35条"], depends=["contract_terms_changed"],
            risk="中"))
    gaps.append("合同类争议需先确认您想主张什么：补签、二倍工资、确认无固定期限、"
                "还是撤销调岗降薪。")
    headline = "合同订立、试用期、文本交付和调岗降薪的规则不同，先定位争议阶段。"
    return Analysis(case_type="labor_contract", as_of="", headline=headline,
                    findings=findings, gaps=gaps, assumptions=[],
                    metadata={"state_revision": revision})


def assess_procedure(facts: dict, today: str | None = None,
                     revision: int = 0) -> Analysis:
    findings: list[Finding] = []
    gaps: list[str] = []
    findings.append(Finding(
        id="F_PR_PRE", issue="仲裁前置",
        conclusion="劳动争议一般应先申请劳动仲裁，对仲裁裁决不服才能向法院起诉；"
                   "但追索劳动报酬可依法申请支付令。",
        reasoning="仲裁前置是劳动争议程序的基本规则。",
        cites=["labor_dispute@2008-05-01:第5条", "labor_contract@2008-01-01:第30条"],
        risk="中"))
    findings.append(Finding(
        id="F_PR_FINAL", issue="一裁终局",
        conclusion="追索劳动报酬、工伤医疗费、经济补偿或赔偿金，不超过当地月最低工资标准"
                   "十二个月金额的，以及执行劳动标准（工时、休息休假、社保）的争议，"
                   "仲裁裁决为终局裁决；但只约束用人单位——劳动者仍可在 15 日内起诉。",
        reasoning="用人单位不服终局裁决，只能在 30 日内向中院申请撤销，不能直接起诉。",
        cites=["labor_dispute@2008-05-01:第47条", "labor_dispute@2008-05-01:第48条",
               "labor_dispute@2008-05-01:第49条"], risk="中"))
    findings.append(Finding(
        id="F_PR_TIME", issue="审限与起诉期限",
        conclusion="仲裁庭应在受理之日起 45 日内结案，复杂案件可延长 15 日；"
                   "不服非终局裁决的，应在收到裁决书之日起 15 日内起诉。",
        reasoning="逾期未作出裁决的，当事人可以就该劳动争议事项向法院起诉。",
        cites=["labor_dispute@2008-05-01:第43条", "labor_dispute@2008-05-01:第48条"],
        risk="中"))
    findings.append(Finding(
        id="F_PR_JURIS", issue="管辖",
        conclusion="由劳动合同履行地或用人单位所在地的劳动争议仲裁委员会管辖；"
                   "双方分别申请的，由履行地仲裁委管辖。",
        reasoning="选对管辖地可以降低往返成本。",
        cites=["labor_dispute@2008-05-01:第21条"], depends=["work_location"], risk="低"))
    if facts.get("arbitration_filed") == "已申请" and facts.get("arbitration_result") == "已裁决":
        gaps.append("已裁决的案件需核对裁决类型（终局/非终局）、送达日期和起诉期限。")
    headline = "劳动争议先仲裁后诉讼；是否一裁终局、下一步怎么走，取决于争议类型和金额。"
    return Analysis(case_type="labor_procedure", as_of="", headline=headline,
                    findings=findings, gaps=gaps, assumptions=[],
                    metadata={"state_revision": revision})


ANALYSERS = {
    "labor_dismissal": assess_dismissal,
    "labor_wage": assess_wage,
    "labor_overtime": assess_overtime,
    "labor_double_pay": assess_double_pay,
    "labor_work_injury": assess_work_injury,
    "labor_social_insurance": assess_social_insurance,
    "labor_annual_leave": assess_annual_leave,
    "labor_noncompete": assess_noncompete,
    "labor_maternity": assess_maternity,
    "labor_dispatch": assess_dispatch,
    "labor_contract": assess_contract,
    "labor_procedure": assess_procedure,
    "tort_injury": assess_tort,
}


def analyse_many(claims: list[str], facts: dict, today: str | None = None,
                 revision: int = 0) -> Analysis:
    """Run every active claim and merge the findings into one memo."""
    analyses: list[Analysis] = []
    gaps: list[str] = []
    for claim in claims:
        fn = ANALYSERS.get(claim)
        if not fn:
            gaps.append(f"暂不支持「{claim}」的自动分析。")
            continue
        try:
            analyses.append(fn(facts, today, revision))
        except Exception as exc:  # keep the consultation alive
            gaps.append(f"{claim} 分析出错：{type(exc).__name__}: {exc}")
    if not analyses:
        return Analysis(case_type=claims[0] if claims else "", as_of="",
                        headline="目前没有可分析的请求权。", findings=[], gaps=gaps,
                        assumptions=[], metadata={"claims": claims})
    findings: list[Finding] = []
    seen: set[str] = set()
    for a in analyses:
        for f in a.findings:
            if f.id in seen:
                continue
            seen.add(f.id)
            findings.append(f)
    headline = "\n\n".join(
        f"**{CLAIM_LABELS.get(a.case_type, a.case_type)}**：{a.headline}"
        for a in analyses if a.headline)
    for a in analyses:
        gaps.extend(g for g in a.gaps if g not in gaps)
    assumptions: list[str] = []
    for a in analyses:
        assumptions.extend(x for x in a.assumptions if x not in assumptions)
    # Keep the old top-level metadata contract for the single-claim case
    # (the eval protocol reads limitation/compensation/illegal/interp there),
    # while exposing every claim's metadata under per_claim.
    meta: dict = {"claims": claims,
                  "per_claim": {a.case_type: a.metadata for a in analyses},
                  "state_revision": revision}
    for key in ("illegal", "compensation", "limitation", "interp", "reason",
                "confidence"):
        for a in analyses:
            if key in a.metadata and key not in meta:
                meta[key] = a.metadata[key]
                break
    return Analysis(
        case_type=analyses[0].case_type, as_of=analyses[0].as_of,
        headline=headline, findings=findings, gaps=gaps, assumptions=assumptions,
        metadata=meta,
    )


def analyse(case_type: str, facts: dict, today: str | None = None,
            revision: int = 0) -> Analysis:
    fn = ANALYSERS.get(case_type)
    if not fn:
        raise ValueError(f"unknown case type: {case_type}")
    return fn(facts, today, revision)

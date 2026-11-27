"""Worker-facing guides: arbitration vs litigation, rights map, checklists.

These are intentionally *explanatory*, not predictive.  They encode the
procedural rules in the corpus and the practical channels workers actually use.
"""
from __future__ import annotations

import json

from .config import DATA
from .elements import ElementSchema
from .memory import CaseState

RIGHTS_PATH = DATA / "knowledge" / "worker_rights_map.json"


def compare_arbitration_litigation(state: CaseState, schema: ElementSchema,
                                   claim: str | None = None) -> str:
    """Markdown comparison tailored to the user's claim/amount."""
    claims = state.claims or ([claim] if claim else [])
    amount = state.value("amount_in_dispute")
    rows = [
        ("性质", "劳动争议一般**仲裁前置**，未经仲裁不能直接起诉（欠薪可申请支付令）。",
         "对仲裁裁决不服，或仲裁委逾期未裁决，才能向法院起诉。"),
        ("管辖", "劳动合同履行地或用人单位所在地的劳动人事争议仲裁委员会。",
         "仲裁委所在地或被告住所地的基层人民法院。"),
        ("时效/期限", "仲裁时效一般 1 年；劳动关系存续期间的欠薪不受 1 年限制。",
         "不服非终局裁决：收到裁决书 15 日内起诉；终局裁决：单位 30 日内向中院申请撤销。"),
        ("审理期限", "受理后 45 日内结案，复杂案件可延长 15 日。",
         "一审普通程序一般 3-6 个月；简易程序 3 个月。"),
        ("费用", "劳动仲裁**不收费**。",
         "劳动争议案件每件 10 元（《诉讼费用交纳办法》），可申请缓交/免交。"),
        ("一裁终局", "小额争议（不超过当地月最低工资 12 个月金额）和执行劳动标准的争议，"
                     "裁决对**用人单位**终局；劳动者仍可 15 日内起诉。",
         "非终局裁决双方都可起诉；终局裁决用人单位只能申请撤销，不能直接起诉。"),
        ("执行", "裁决生效后对方不履行，可向法院申请**强制执行**；符合条件的可申请先予执行。",
         "判决/调解书生效后同样可申请强制执行。"),
        ("优点", "快、免费、门槛低；很多案件在仲裁阶段就调解结案。",
         "程序更完整、可上诉；适合金额大、法律关系复杂的案件。"),
        ("缺点", "一裁终局对单位有利；部分请求（如补缴社保、公积金）不归仲裁管。",
         "周期长、成本高；劳动争议标的小，诉讼性价比未必高。"),
    ]
    lines = ["# 仲裁 vs 诉讼：劳动争议怎么选", ""]
    if claims:
        lines.append("**您的请求类型：** " + "、".join(schema.label(c) for c in claims))
        lines.append("")
    if isinstance(amount, (int, float)):
        lines.append(f"**您主张的金额：** {amount:,.0f} 元。"
                     "是否一裁终局要看**单项请求**是否超过当地月最低工资的 12 倍，"
                     "不能只看总额。")
        lines.append("")
    lines += ["| 维度 | 劳动仲裁 | 劳动诉讼 |", "|---|---|---|"]
    for a, b, c in rows:
        lines.append(f"| {a} | {b} | {c} |")
    lines += [
        "",
        "## 实务建议",
        "",
        "1. **先仲裁**：劳动争议不能绕过仲裁直接起诉（欠薪支付令除外）。",
        "2. **先算时效**：仲裁时效一般 1 年；欠薪在劳动关系存续期间有特殊规则，"
        "但离职后要在 1 年内提出。",
        "3. **看清裁决类型**：收到裁决书先看是否写明“终局裁决”；"
        "劳动者不服终局裁决仍可 15 日内起诉。",
        "4. **补缴社保/公积金**：一般不归仲裁管，向社保征收机构/公积金中心投诉更直接。",
        "5. **金额小、事实清楚**：仲裁更划算；金额大、涉及复杂法律争点："
        "仲裁后视情况起诉。",
        "",
        "> 本对比是通用规则，具体管辖、费用和终局标准以当地仲裁委/法院为准。",
    ]
    return "\n".join(lines)


def worker_rights_map() -> str:
    raw = json.loads(RIGHTS_PATH.read_text(encoding="utf-8"))
    lines = ["# 打工人权益地图", "",
             "按“入职前 → 在职 → 离职 → 维权”整理。每一项都可以直接来问我，"
             "我会按要件追问，而不是套模板。", ""]
    for stage in raw.get("stages", []):
        lines.append(f"## {stage['label']}")
        lines.append("")
        for t in stage.get("topics", []):
            lines.append(f"- **{t['title']}**：{t['tip']}")
        lines.append("")
    lines.append("## 常用渠道")
    lines.append("")
    for c in raw.get("channels", []):
        lines.append(f"- **{c['name']}**：{c['use']}")
    lines.append("")
    lines.append("> 本地图是信息整理，不构成法律意见；具体政策以当地人社/法院口径为准。")
    return "\n".join(lines)


def arbitration_checklist(state: CaseState, schema: ElementSchema) -> str:
    lines = ["# 劳动仲裁材料清单", ""]
    lines += [
        "## 必备材料",
        "- [ ] 仲裁申请书（按被申请人人数 +1 份）",
        "- [ ] 申请人身份证复印件",
        "- [ ] 被申请人主体信息（国家企业信用信息公示系统打印）",
        "- [ ] 劳动关系证明（劳动合同、工资流水、社保记录、工牌、考勤等）",
        "- [ ] 证据清单及证据复印件（原件开庭时带）",
        "- [ ] 授权委托书/法律援助材料（如委托代理人）",
        "",
        "## 按请求补充",
    ]
    mapping = {
        "labor_dismissal": "解除通知书、离职证明、规章制度及签收记录、工会通知、补偿支付记录",
        "labor_wage": "工资条、银行流水、欠条、考勤、催款聊天记录",
        "labor_overtime": "考勤打卡、排班表、加班审批、工作群记录",
        "labor_double_pay": "入职登记、工资流水、未签合同的沟通记录",
        "labor_work_injury": "工伤认定书、劳动能力鉴定结论、病历、医疗费票据",
        "labor_social_insurance": "社保缴费明细、断缴记录、工资流水",
        "labor_annual_leave": "工龄证明、年假申请/审批记录、工资流水",
        "labor_noncompete": "竞业限制协议、补偿支付记录、新单位劳动合同",
        "labor_maternity": "怀孕/生育证明、产假审批、生育津贴发放记录",
        "labor_dispatch": "派遣/外包协议、考勤/派单记录、工资发放主体",
    }
    for claim in (state.claims or []):
        if claim in mapping:
            lines.append(f"- [ ] {schema.label(claim)}：{mapping[claim]}")
    lines += ["", "> 各地仲裁委材料要求略有差异，提交前先电话/官网核对。"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 期限卡片 & 合同条款体检
# ---------------------------------------------------------------------------
def deadline_card(state: CaseState, schema: ElementSchema,
                  today: str | None = None) -> str:
    """A short, dated checklist of the deadlines that actually bite."""
    from .rules import check_limitation
    today = today or "2026-11-27"
    lines = ["# 关键期限卡片", ""]
    claims = state.claims or []
    anchor = state.value("dismiss_date") or state.value("injury_date") or ""
    if "labor_dismissal" in claims and anchor:
        lim = check_limitation("labor_dismissal", str(anchor), today)
        if lim.get("ok"):
            status = "⚠️ 可能已过" if lim["expired"] else f"剩余约 {lim['days_left']} 天"
            lines.append(f"- **仲裁时效**：自 {lim['start']} 起算，"
                         f"{lim['deadline']} 届满（{status}）。")
    if "labor_wage" in claims:
        lines.append("- **欠薪时效**：劳动关系存续期间不受 1 年限制；"
                     "劳动关系终止的，自终止之日起 1 年内提出。")
    if "labor_work_injury" in claims:
        anchor_i = state.value("injury_date")
        if anchor_i:
            lines.append(f"- **工伤认定**：单位应在 {anchor_i} 起 30 日内申请；"
                         "单位不申请的，个人应在 1 年内申请。")
        lines.append("- **停工留薪期**：一般不超过 12 个月，延长需劳动能力鉴定委员会确认。")
        lines.append("- **劳动能力鉴定**：伤情相对稳定后申请；鉴定结论影响待遇。")
    if "labor_annual_leave" in claims:
        lines.append("- **年假时效**：很多地区按年度分别起算 1 年，陈年未休年假容易过期。")
    if "labor_noncompete" in claims:
        lines.append("- **竞业限制**：单位 3 个月未付补偿，可请求解除；"
                     "违约金争议注意仲裁时效。")
    if "labor_procedure" in claims or "arbitration_filed" in (state.values() or {}):
        if state.value("arbitration_filed") == "已申请":
            lines.append("- **仲裁审限**：受理后 45 日内结案，复杂案件可延长 15 日。")
            lines.append("- **不服裁决**：非终局裁决收到裁决书 15 日内起诉；"
                         "终局裁决单位 30 日内向中院申请撤销。")
    if len(lines) == 2:
        lines.append("- 还没有足够的日期信息。先告诉我解除/受伤/欠薪的时间，我再算期限。")
    lines += ["", "> 期限按自然日计算；最后一日遇法定节假日可能顺延，具体以法律规定为准。"]
    return "\n".join(lines)


CONTRACT_RISKS = [
    (r"自愿放弃.{0,6}(社保|社会保险)|不缴社保|社保补贴", "高",
     "放弃社保的约定无效；单位仍可能被要求补缴，你也可据此被迫解除主张经济补偿。",
     "labor_js2@2025-09-01:第19条"),
    (r"押金|保证金|扣押.{0,4}(身份证|证件|毕业证)", "高",
     "用人单位不得收取押金或扣押证件；可向劳动监察投诉。",
     "labor_contract@2008-01-01:第9条"),
    (r"空白合同|先签字|合同.{0,6}空白", "高",
     "空白合同不等于有效订立；签字前应要求填写完整并保留一份。",
     "labor_js2@2025-09-01:第6条"),
    (r"竞业限制|竞业禁止", "中",
     "竞业限制只适用于高管/高技/保密人员，期限不超过 2 年，单位应按月支付补偿。",
     "labor_contract@2008-01-01:第23条"),
    (r"违约金", "中",
     "普通劳动者只有服务期和竞业限制两种情形可以约定违约金；其他违约金条款可能无效。",
     "labor_contract@2008-01-01:第25条"),
    (r"试用期.{0,10}(六个月|6个月|一年|12个月)", "中",
     "试用期上限与合同期限挂钩：3 年以上/无固定期限最多 6 个月。",
     "labor_contract@2008-01-01:第19条"),
    (r"996|大小周|单休|每周工作六天|月休四天", "高",
     "超出标准工时的部分原则上应支付加班费；特殊工时需审批并告知。",
     "labor_law@1995-01-01:第36条"),
    (r"加班.{0,6}(审批|申请)|未审批.{0,6}不算加班|调休.{0,6}过期", "中",
     "内部审批/调休过期规则不能当然排除法定加班费；隐形加班也可能被认定。",
     "labor_js1@2021-01-01:第42条"),
    (r"随时.{0,6}(调岗|调薪|调整工作地点)|公司有权单方", "中",
     "调岗降薪变更劳动合同应协商一致并书面；单方变更可拒绝或主张补差。",
     "labor_contract@2008-01-01:第35条"),
    (r"工伤.{0,8}(自负|自行负责|与公司无关)|生死状", "高",
     "工伤责任是法定的，不能通过协议免除；单位未参保则由单位支付待遇。",
     "work_injury_reg@2011-01-01:第62条"),
    (r"不得.{0,4}(怀孕|生育)|限制生育|入职.{0,6}(怀孕|生育)", "高",
     "限制生育的条款违法；三期女职工受特殊保护。",
     "female_protection@2012-04-28:第5条"),
    (r"离职.{0,6}(批准|同意)|不批.{0,6}不能走|扣.{0,4}工资", "中",
     "劳动者提前 30 日书面通知即可解除，无需单位批准；不得克扣工资。",
     "labor_contract@2008-01-01:第37条"),
    (r"自愿加班|放弃加班费|加班费.{0,6}包含在工资", "中",
     "“自愿加班/放弃加班费”的约定可能被认定排除法定权利，需结合实际情况判断。",
     "labor_law@1995-01-01:第44条"),
]


def audit_contract(text: str) -> str:
    """Rule-based first pass over a contract clause.  Flags, not legal advice."""
    import re
    text = text or ""
    hits = []
    for pattern, risk, why, basis in CONTRACT_RISKS:
        for m in re.finditer(pattern, text):
            start = max(0, m.start() - 18)
            end = min(len(text), m.end() + 18)
            hits.append((risk, m.group(0), text[start:end].replace("\n", " "), why, basis))
            break
    lines = ["# 劳动合同条款体检（草稿）", ""]
    if not hits:
        lines.append("没有命中常见的明显风险条款。但“没写”也可能是风险："
                     "试用期、工资构成、工作地点、竞业限制、加班费基数都应当写清楚。")
    else:
        lines.append(f"共命中 {len(hits)} 类风险点，按严重程度排序：")
        lines.append("")
        order = {"高": 0, "中": 1, "低": 2}
        for risk, term, context, why, basis in sorted(hits, key=lambda x: order[x[0]]):
            lines.append(f"## [{risk}] {term}")
            lines.append("")
            lines.append(f"> …{context}…")
            lines.append("")
            lines.append(why)
            lines.append("")
            lines.append(f"依据：{basis}")
            lines.append("")
    lines += [
        "## 签字前建议",
        "",
        "- [ ] 要求公司把空白处填完整，双方各执一份。",
        "- [ ] 工资构成、发薪日、工作地点、岗位写清楚。",
        "- [ ] 试用期长度和工资符合法定上限。",
        "- [ ] 竞业限制要有补偿标准；普通岗位可拒绝签。",
        "- [ ] 对“自愿放弃”“公司可随时调整”这类条款，保留书面异议。",
        "",
        "> 本体检只做关键词和规则初筛，不能替代对完整合同的审查。",
    ]
    return "\n".join(lines)

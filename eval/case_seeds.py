"""Curated synthetic seeds, not claimed to be real judgments or lawyer labels."""
from __future__ import annotations

COMMON = {
    "employer": "青禾技术有限公司", "actual_employer": "远帆制造有限公司",
    "position": "技术支持", "work_location": "上海", "start_date": "2021-03-01",
    "dismiss_date": "2026-03-15", "monthly_wage": 10000,
    "contract_signed": "已签书面合同", "contract_type": "固定期限",
    "contract_copies": "我有一份", "probation": "有试用期", "probation_length": 2,
    "probation_wage": 8500, "illegal_probation": "没有", "contract_terms_changed": "没有",
    "social_insurance": "未缴纳", "social_insurance_years": 5,
    "social_insurance_gap": "2026年1月至2月", "housing_fund": "正常缴纳",
    "social_insurance_claim": "要求补缴", "work_schedule": "标准工时",
    "arbitration_filed": "已申请", "arbitration_date": "2026-04-10",
    "arbitration_result": "已受理", "court_filed": "没有起诉",
    "amount_in_dispute": 20000, "claim_type": "要求赔偿金", "deadline_aware": "知道，还没过",
    "who_initiated": "单位单方解除", "stated_reason": "严重违纪",
    "rule_exists": "有成文制度", "rule_publicized": "没有公示告知",
    "rule_democratic": "没有经过", "misconduct_proof": "只有口头指认",
    "training_or_transfer": "没有", "notice_30d": "都没有", "union_notified": "没有通知",
    "forced_resignation_reason": "不适用", "compensation_paid": "未支付任何补偿",
    "pregnancy_status": "孕期", "contract_expired": "合同期内解除",
    "wage_owed": 20000, "wage_period": "2026年1月至2月", "wage_type": "基本工资",
    "wage_reason": "无故拖欠", "wage_evidence": "银行流水", "reduced_salary": "没有被降薪",
    "overtime_exists": "有", "overtime_period": "2026年2月", "overtime_hours_weekday": 20,
    "overtime_hours_rest": 16, "overtime_hours_holiday": 8,
    "overtime_evidence": "考勤打卡", "overtime_paid": "没有支付",
    "no_contract_months": 5, "demand_contract": "提出过",
    "injury_date": "2026-02-01", "injury_at_work": "工作时间和场所内",
    "injury_reported": "单位30日内申请", "injury_recognized": "已认定工伤",
    "disability_level": "十级", "medical_cost": 12000,
    "work_injury_insurance": "参加了工伤保险", "injury_evidence": "医院病历",
    "cumulative_work_years": 9, "annual_leave_taken": 2, "annual_leave_year": "2025",
    "annual_leave_paid": "没有支付", "noncompete_signed": "签了竞业限制协议",
    "noncompete_months": 12, "noncompete_compensation": 4000,
    "noncompete_paid": "没有支付", "noncompete_claim": "要求支付补偿",
    "new_employer_competitor": "没有去", "maternity_leave_taken": "还没休",
    "maternity_allowance": "单位发工资", "maternity_dismissal": "被降薪或调岗",
    "dispatch_type": "劳务派遣", "work_management": "打卡考勤",
    "pay_by": "青禾技术有限公司", "platform_worker": "不是", "uniform_tools": "穿工服/用公司工具",
}

# Each tuple: primary claim, opening, annotated opening facts, correction, challenge patch.
SEEDS = [
 ("labor_dismissal", "公司把我辞退了，说我严重违纪，我想问赔偿。",
  {"who_initiated": "单位单方解除", "stated_reason": "严重违纪"},
  ("dismiss_date", "2026-09-15"), {"stated_reason": "不胜任工作", "start_date": "2026-03-01"}),
 ("labor_wage", "公司拖欠工资，我想追回欠薪。", {},
  ("wage_owed", 25000), {"wage_type": "提成/奖金", "wage_reason": "以绩效为由扣发"}),
 ("labor_overtime", "公司一直没有支付加班费，我想算一下。",
  {"overtime_exists": "有", "overtime_paid": "没有支付"},
  ("overtime_hours_weekday", 30), {"overtime_exists": "没有"}),
 ("labor_double_pay", "入职后一直没签书面合同，我想问二倍工资。",
  {"contract_signed": "未签书面合同"}, ("no_contract_months", 7),
  {"contract_signed": "已签书面合同"}),
 ("labor_work_injury", "我想咨询工伤认定和伤残待遇，要先准备什么？", {},
  ("disability_level", "九级"), {"injury_at_work": "因工外出", "work_injury_insurance": "没有参加"}),
 ("labor_social_insurance", "公司没交社保，我想问补缴的事情。",
  {"social_insurance": "未缴纳", "social_insurance_claim": "要求补缴"},
  ("social_insurance_claim", "要求被迫解除经济补偿"), {"social_insurance": "正常缴纳"}),
 ("labor_annual_leave", "我有未休年假，想问年假工资怎么计算。", {},
  ("cumulative_work_years", 10), {"cumulative_work_years": 20}),
 ("labor_noncompete", "签了竞业限制协议，公司没有支付竞业补偿。",
  {"noncompete_signed": "签了竞业限制协议", "noncompete_paid": "没有支付"},
  ("noncompete_months", 18), {"noncompete_signed": "没有签"}),
 ("labor_maternity", "我在孕期，公司降低了工资待遇，想了解生育保护。",
  {"pregnancy_status": "孕期", "maternity_dismissal": "被降薪或调岗"},
  ("maternity_dismissal", "因怀孕/生育被辞退"), {"pregnancy_status": "哺乳期"}),
 ("labor_dispatch", "我是劳务派遣员工，想确认劳动关系和责任单位。",
  {"dispatch_type": "劳务派遣", "claim_type": "要求确认劳动关系"},
  ("dispatch_type", "业务外包"), {"dispatch_type": "平台/新业态用工", "platform_worker": "外卖骑手"}),
 ("labor_contract", "我想咨询试用期和劳动合同变更。", {},
  ("contract_terms_changed", "被单方变更"), {"probation": "没有试用期"}),
 ("labor_procedure", "我已经申请劳动仲裁，想了解后续程序。",
  {"arbitration_filed": "已申请"}, ("arbitration_result", "已裁决"), {}),
]

OVERRIDES = {
 "labor_double_pay": {"contract_signed": "未签书面合同", "claim_type": "要求支付二倍工资"},
 "labor_wage": {"claim_type": "要求支付欠薪"},
 "labor_overtime": {"claim_type": "要求支付加班费"},
 "labor_work_injury": {"claim_type": "要求工伤待遇"},
 "labor_social_insurance": {"claim_type": "要求补缴社保"},
 "labor_annual_leave": {"claim_type": "要求支付年假工资"},
 "labor_noncompete": {"claim_type": "要求支付竞业限制补偿"},
 "labor_dispatch": {"claim_type": "要求确认劳动关系"},
 "labor_maternity": {"claim_type": "要求继续履行"},
 "labor_contract": {"claim_type": "还没想好"},
}

UNKNOWN_KEYS = {"labor_annual_leave": "monthly_wage", "labor_noncompete": "monthly_wage",
                "labor_maternity": "maternity_allowance", "labor_dispatch": "actual_employer",
                "labor_contract": "contract_type", "labor_procedure": "arbitration_date"}

TEMPLATES = {
 "start_date": "我是{v}入职的。", "dismiss_date": "离职解除日期是{v}。",
 "injury_date": "受伤日期是{v}。", "arbitration_date": "申请仲裁日期是{v}。",
 "monthly_wage": "月平均工资是{v}元。", "employer": "公司全称是{v}。",
 "actual_employer": "实际用工单位是{v}。", "wage_owed": "公司欠我工资{v}元。",
 "wage_period": "欠薪期间是{v}。", "overtime_period": "加班期间是{v}。",
 "overtime_exists": "{v}加班。", "rule_publicized": "员工手册{v}。",
 "rule_exists": "公司{v}。", "rule_democratic": "民主程序方面，{v}。",
 "misconduct_proof": "违纪证据方面，{v}。", "union_notified": "工会方面，{v}。",
 "training_or_transfer": "培训或调岗方面，{v}。", "notice_30d": "提前通知和代通知金方面，{v}。",
 "stated_reason": "公司的解除理由是{v}。", "who_initiated": "解除主体是{v}。",
 "overtime_hours_weekday": "工作日每月加班{v}小时。",
 "overtime_hours_rest": "休息日每月加班{v}小时。",
 "overtime_hours_holiday": "法定节假日每月加班{v}小时。",
 "overtime_paid": "加班费{v}。", "no_contract_months": "没签合同{v}个月。",
 "contract_signed": "书面劳动合同方面，{v}。", "probation_length": "试用期是{v}个月。",
 "probation_wage": "试用期工资是{v}元。", "annual_leave_taken": "已经休了{v}天年假。",
 "cumulative_work_years": "累计工作{v}年。", "noncompete_months": "竞业限制期限是{v}个月。",
 "noncompete_compensation": "竞业补偿约定每月{v}元。", "medical_cost": "医疗费{v}元。",
 "social_insurance": "社保缴纳情况是{v}。", "claim_type": "我的诉求是{v}。",
 "amount_in_dispute": "争议金额是{v}元。",
}

SOURCES = {
 "labor_contract": "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0",
 "labor_js1": "https://www.court.gov.cn/zixun/xiangqing/282121.html",
 "annual_leave": "https://xzfg.moj.gov.cn/front/law/detail?LawID=208",
 "annual_leave_implementation": "https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf",
 "work_injury": "https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610",
 "official_database": "https://flk.npc.gov.cn/",
}


def answer_text(key, value, facts_catalog):
    if value is None:
        return f"关于{facts_catalog[key]['label']}，这个我确实不清楚，没有材料确认。"
    if key == "overtime_exists":
        return "有加班。" if value == "有" else "没有加班。"
    if key == "overtime_paid":
        return "公司没有支付加班费。" if value == "没有支付" else f"加班费{value}。"
    if key == "noncompete_signed":
        return "没签竞业限制协议。" if value == "没有签" else "签了竞业限制协议。"
    template = TEMPLATES.get(key, "关于" + facts_catalog[key]["label"] + "，{v}。")
    return template.format(v=f"{value:g}" if isinstance(value, (int, float)) else value)

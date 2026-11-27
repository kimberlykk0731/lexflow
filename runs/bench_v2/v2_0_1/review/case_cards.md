# Bench v2 案例卡

所有案例为合成；人工法律审定尚未完成。下列 gold 不可直接称为法律正确答案。

## B01 · labor_dismissal · dev

公司把我辞退了，说我严重违纪，我想问赔偿。

```json
{
  "claims_gold": [
    "labor_dismissal"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求赔偿金",
    "compensation_paid": "未支付任何补偿",
    "contract_expired": "合同期内解除",
    "contract_signed": "已签书面合同",
    "deadline_aware": "知道，还没过",
    "dismiss_date": "2026-03-15",
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "misconduct_proof": "只有口头指认",
    "monthly_wage": 10000,
    "notice_30d": "都没有",
    "pregnancy_status": "孕期",
    "rule_democratic": "没有经过",
    "rule_exists": "有成文制度",
    "rule_publicized": "没有公示告知",
    "start_date": "2021-03-01",
    "stated_reason": "严重违纪",
    "training_or_transfer": "没有",
    "union_notified": "没有通知",
    "who_initiated": "单位单方解除"
  },
  "critical": [
    "claim_type",
    "contract_signed",
    "dismiss_date",
    "employer",
    "misconduct_proof",
    "monthly_wage",
    "rule_democratic",
    "rule_exists",
    "rule_publicized",
    "start_date",
    "stated_reason",
    "union_notified",
    "who_initiated"
  ],
  "gold_before": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "stated_reason",
        "rule_publicized"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "2N",
      "expected": 110000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "stated_reason",
        "rule_publicized"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "2N",
      "expected": 110000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B02 · labor_dismissal · test

公司把我辞退了，说我严重违纪，我想问赔偿。

```json
{
  "claims_gold": [
    "labor_dismissal"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求赔偿金",
    "compensation_paid": "未支付任何补偿",
    "contract_expired": "合同期内解除",
    "contract_signed": "已签书面合同",
    "deadline_aware": "知道，还没过",
    "dismiss_date": "2026-03-15",
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "misconduct_proof": "只有口头指认",
    "monthly_wage": 12000,
    "notice_30d": "都没有",
    "pregnancy_status": "孕期",
    "rule_democratic": "没有经过",
    "rule_exists": "有成文制度",
    "rule_publicized": "没有公示告知",
    "start_date": "2020-04-01",
    "stated_reason": "严重违纪",
    "training_or_transfer": "没有",
    "union_notified": "没有通知",
    "who_initiated": "单位单方解除"
  },
  "critical": [
    "claim_type",
    "contract_signed",
    "dismiss_date",
    "employer",
    "misconduct_proof",
    "monthly_wage",
    "rule_democratic",
    "rule_exists",
    "rule_publicized",
    "start_date",
    "stated_reason",
    "union_notified",
    "who_initiated"
  ],
  "gold_before": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "stated_reason",
        "rule_publicized"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "2N",
      "expected": 144000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "stated_reason",
        "rule_publicized"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "2N",
      "expected": 156000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-09-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "dismiss_date", "old": "2026-03-15", "new": "2026-09-15", "text": "更正一下，我之前说错了。离职解除日期是2026-09-15。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B03 · labor_dismissal · test

我想咨询解除/辞退，情况需要核实，能先帮我梳理吗？另外还涉及工资/欠薪。

```json
{
  "claims_gold": [
    "labor_dismissal",
    "labor_wage"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求支付欠薪",
    "compensation_paid": "未支付任何补偿",
    "contract_expired": "合同期内解除",
    "contract_signed": "已签书面合同",
    "deadline_aware": "知道，还没过",
    "dismiss_date": "2026-03-15",
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "misconduct_proof": "只有口头指认",
    "monthly_wage": 10000,
    "notice_30d": "都没有",
    "pregnancy_status": "孕期",
    "reduced_salary": "没有被降薪",
    "rule_democratic": "没有经过",
    "rule_exists": "有成文制度",
    "rule_publicized": "没有公示告知",
    "start_date": "2026-03-01",
    "stated_reason": "不胜任工作",
    "training_or_transfer": "没有",
    "union_notified": "没有通知",
    "wage_evidence": "银行流水",
    "wage_owed": 5000,
    "wage_period": "2026年3月",
    "wage_reason": "无故拖欠",
    "wage_type": "基本工资",
    "who_initiated": "单位单方解除"
  },
  "critical": [
    "claim_type",
    "contract_signed",
    "dismiss_date",
    "employer",
    "monthly_wage",
    "notice_30d",
    "start_date",
    "stated_reason",
    "training_or_transfer",
    "union_notified",
    "wage_evidence",
    "wage_owed",
    "wage_period",
    "wage_type",
    "who_initiated"
  ],
  "gold_before": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "stated_reason",
        "rule_publicized"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "2N",
      "expected": 10000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_wage",
      "path": "finding_money:F_WAGE_AMOUNT",
      "calculator": "fact",
      "depends": [
        "wage_owed"
      ],
      "field": "wage_owed",
      "tolerance": 0.5,
      "expected": 5000,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "stated_reason",
        "rule_publicized"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "2N",
      "expected": 10000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_wage",
      "path": "finding_money:F_WAGE_AMOUNT",
      "calculator": "fact",
      "depends": [
        "wage_owed"
      ],
      "field": "wage_owed",
      "tolerance": 0.5,
      "expected": 5000,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B04 · labor_wage · dev

公司拖欠工资，我想追回欠薪。

```json
{
  "claims_gold": [
    "labor_wage"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "employer": "青禾技术有限公司",
    "monthly_wage": 10000,
    "reduced_salary": "没有被降薪",
    "start_date": "2021-03-01",
    "wage_evidence": "银行流水",
    "wage_owed": 20000,
    "wage_period": "2026年1月至2月",
    "wage_reason": "无故拖欠",
    "wage_type": "基本工资"
  },
  "critical": [
    "monthly_wage",
    "start_date",
    "wage_evidence",
    "wage_owed",
    "wage_period",
    "wage_type"
  ],
  "gold_before": [
    {
      "claim": "labor_wage",
      "path": "finding_money:F_WAGE_AMOUNT",
      "calculator": "fact",
      "depends": [
        "wage_owed"
      ],
      "field": "wage_owed",
      "tolerance": 0.5,
      "expected": 20000,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_wage",
      "path": "finding_money:F_WAGE_AMOUNT",
      "calculator": "fact",
      "depends": [
        "wage_owed"
      ],
      "field": "wage_owed",
      "tolerance": 0.5,
      "expected": 20000,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B05 · labor_wage · test

公司拖欠工资，我想追回欠薪。

```json
{
  "claims_gold": [
    "labor_wage"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "employer": "青禾技术有限公司",
    "monthly_wage": 12000,
    "reduced_salary": "没有被降薪",
    "start_date": "2020-04-01",
    "wage_evidence": "银行流水",
    "wage_owed": 24000,
    "wage_period": "2026年1月至2月",
    "wage_reason": "无故拖欠",
    "wage_type": "基本工资"
  },
  "critical": [
    "monthly_wage",
    "start_date",
    "wage_evidence",
    "wage_owed",
    "wage_period",
    "wage_type"
  ],
  "gold_before": [
    {
      "claim": "labor_wage",
      "path": "finding_money:F_WAGE_AMOUNT",
      "calculator": "fact",
      "depends": [
        "wage_owed"
      ],
      "field": "wage_owed",
      "tolerance": 0.5,
      "expected": 24000,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_wage",
      "path": "finding_money:F_WAGE_AMOUNT",
      "calculator": "fact",
      "depends": [
        "wage_owed"
      ],
      "field": "wage_owed",
      "tolerance": 0.5,
      "expected": 25000,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "wage_owed", "old": 24000, "new": 25000, "text": "更正一下，我之前说错了。公司欠我工资25000元。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B06 · labor_wage · test

我想咨询工资/欠薪，情况需要核实，能先帮我梳理吗？另外还涉及加班费。

```json
{
  "claims_gold": [
    "labor_wage",
    "labor_overtime"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "employer": "青禾技术有限公司",
    "monthly_wage": 10000,
    "overtime_evidence": "考勤打卡",
    "overtime_exists": "有",
    "overtime_hours_holiday": 8,
    "overtime_hours_rest": 16,
    "overtime_hours_weekday": 20,
    "overtime_paid": "没有支付",
    "overtime_period": "2026年2月",
    "reduced_salary": "没有被降薪",
    "start_date": "2021-03-01",
    "wage_evidence": "银行流水",
    "wage_owed": 20000,
    "wage_period": "2026年1月至2月",
    "wage_reason": "以绩效为由扣发",
    "wage_type": "提成/奖金",
    "work_schedule": "标准工时"
  },
  "critical": [
    "monthly_wage",
    "overtime_evidence",
    "overtime_exists",
    "overtime_hours_holiday",
    "overtime_hours_rest",
    "overtime_hours_weekday",
    "overtime_paid",
    "overtime_period",
    "start_date",
    "wage_evidence",
    "wage_owed",
    "wage_period",
    "wage_type",
    "work_schedule"
  ],
  "gold_before": [
    {
      "claim": "labor_wage",
      "path": "finding_money:F_WAGE_AMOUNT",
      "calculator": "fact",
      "depends": [
        "wage_owed"
      ],
      "field": "wage_owed",
      "tolerance": 0.5,
      "expected": 20000,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_overtime",
      "path": "calculation.amount",
      "calculator": "overtime",
      "depends": [
        "monthly_wage",
        "overtime_hours_weekday",
        "overtime_hours_rest",
        "overtime_hours_holiday"
      ],
      "expected": 4942.53,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_wage",
      "path": "finding_money:F_WAGE_AMOUNT",
      "calculator": "fact",
      "depends": [
        "wage_owed"
      ],
      "field": "wage_owed",
      "tolerance": 0.5,
      "expected": 20000,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_overtime",
      "path": "calculation.amount",
      "calculator": "overtime",
      "depends": [
        "monthly_wage",
        "overtime_hours_weekday",
        "overtime_hours_rest",
        "overtime_hours_holiday"
      ],
      "expected": 4942.53,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B07 · labor_overtime · dev

公司一直没有支付加班费，我想算一下。

```json
{
  "claims_gold": [
    "labor_overtime"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "monthly_wage": 10000,
    "overtime_evidence": "考勤打卡",
    "overtime_exists": "有",
    "overtime_hours_holiday": 8,
    "overtime_hours_rest": 16,
    "overtime_hours_weekday": 20,
    "overtime_paid": "没有支付",
    "overtime_period": "2026年2月",
    "start_date": "2021-03-01",
    "work_schedule": "标准工时"
  },
  "critical": [
    "monthly_wage",
    "overtime_evidence",
    "overtime_exists",
    "overtime_hours_holiday",
    "overtime_hours_rest",
    "overtime_hours_weekday",
    "overtime_paid",
    "overtime_period",
    "start_date",
    "work_schedule"
  ],
  "gold_before": [
    {
      "claim": "labor_overtime",
      "path": "calculation.amount",
      "calculator": "overtime",
      "depends": [
        "monthly_wage",
        "overtime_hours_weekday",
        "overtime_hours_rest",
        "overtime_hours_holiday"
      ],
      "expected": 4942.53,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_overtime",
      "path": "calculation.amount",
      "calculator": "overtime",
      "depends": [
        "monthly_wage",
        "overtime_hours_weekday",
        "overtime_hours_rest",
        "overtime_hours_holiday"
      ],
      "expected": 4942.53,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B08 · labor_overtime · test

公司一直没有支付加班费，我想算一下。

```json
{
  "claims_gold": [
    "labor_overtime"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "monthly_wage": 12000,
    "overtime_evidence": "考勤打卡",
    "overtime_exists": "有",
    "overtime_hours_holiday": 8,
    "overtime_hours_rest": 16,
    "overtime_hours_weekday": 24,
    "overtime_paid": "没有支付",
    "overtime_period": "2026年2月",
    "start_date": "2020-04-01",
    "work_schedule": "标准工时"
  },
  "critical": [
    "monthly_wage",
    "overtime_evidence",
    "overtime_exists",
    "overtime_hours_holiday",
    "overtime_hours_rest",
    "overtime_hours_weekday",
    "overtime_paid",
    "overtime_period",
    "start_date",
    "work_schedule"
  ],
  "gold_before": [
    {
      "claim": "labor_overtime",
      "path": "calculation.amount",
      "calculator": "overtime",
      "depends": [
        "monthly_wage",
        "overtime_hours_weekday",
        "overtime_hours_rest",
        "overtime_hours_holiday"
      ],
      "expected": 6344.83,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_overtime",
      "path": "calculation.amount",
      "calculator": "overtime",
      "depends": [
        "monthly_wage",
        "overtime_hours_weekday",
        "overtime_hours_rest",
        "overtime_hours_holiday"
      ],
      "expected": 6965.52,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "overtime_hours_weekday", "old": 24, "new": 30, "text": "更正一下，我之前说错了。工作日每月加班30小时。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B09 · labor_overtime · test

我想咨询加班费，情况需要核实，能先帮我梳理吗？另外还涉及未签合同二倍工资。

```json
{
  "claims_gold": [
    "labor_overtime",
    "labor_double_pay"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "contract_signed": "未签书面合同",
    "demand_contract": "提出过",
    "employer": "青禾技术有限公司",
    "monthly_wage": 10000,
    "no_contract_months": 5,
    "overtime_evidence": "考勤打卡",
    "overtime_exists": "没有",
    "overtime_hours_holiday": 0,
    "overtime_hours_rest": 0,
    "overtime_hours_weekday": 0,
    "overtime_paid": "没有支付",
    "overtime_period": "2026年2月",
    "start_date": "2021-03-01",
    "work_schedule": "标准工时"
  },
  "critical": [
    "contract_signed",
    "demand_contract",
    "monthly_wage",
    "no_contract_months",
    "overtime_exists",
    "overtime_period",
    "start_date",
    "work_schedule"
  ],
  "gold_before": [
    {
      "claim": "labor_overtime",
      "path": "finding:F_OT_NONE",
      "calculator": "literal",
      "depends": [
        "overtime_exists"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_double_pay",
      "path": "calculation.amount",
      "calculator": "double_pay",
      "depends": [
        "monthly_wage",
        "no_contract_months"
      ],
      "expected": 50000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_overtime",
      "path": "finding:F_OT_NONE",
      "calculator": "literal",
      "depends": [
        "overtime_exists"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_double_pay",
      "path": "calculation.amount",
      "calculator": "double_pay",
      "depends": [
        "monthly_wage",
        "no_contract_months"
      ],
      "expected": 50000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B10 · labor_double_pay · dev

入职后一直没签书面合同，我想问二倍工资。

```json
{
  "claims_gold": [
    "labor_double_pay"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "contract_signed": "未签书面合同",
    "demand_contract": "提出过",
    "employer": "青禾技术有限公司",
    "monthly_wage": 10000,
    "no_contract_months": 5,
    "start_date": "2021-03-01"
  },
  "critical": [
    "contract_signed",
    "demand_contract",
    "monthly_wage",
    "no_contract_months",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_double_pay",
      "path": "calculation.amount",
      "calculator": "double_pay",
      "depends": [
        "monthly_wage",
        "no_contract_months"
      ],
      "expected": 50000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_double_pay",
      "path": "calculation.amount",
      "calculator": "double_pay",
      "depends": [
        "monthly_wage",
        "no_contract_months"
      ],
      "expected": 50000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B11 · labor_double_pay · test

入职后一直没签书面合同，我想问二倍工资。

```json
{
  "claims_gold": [
    "labor_double_pay"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "contract_signed": "未签书面合同",
    "demand_contract": "提出过",
    "employer": "青禾技术有限公司",
    "monthly_wage": 12000,
    "no_contract_months": 5,
    "start_date": "2020-04-01"
  },
  "critical": [
    "contract_signed",
    "demand_contract",
    "monthly_wage",
    "no_contract_months",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_double_pay",
      "path": "calculation.amount",
      "calculator": "double_pay",
      "depends": [
        "monthly_wage",
        "no_contract_months"
      ],
      "expected": 60000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_double_pay",
      "path": "calculation.amount",
      "calculator": "double_pay",
      "depends": [
        "monthly_wage",
        "no_contract_months"
      ],
      "expected": 84000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "no_contract_months", "old": 5, "new": 7, "text": "更正一下，我之前说错了。没签合同7个月。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B12 · labor_double_pay · test

我想咨询未签合同二倍工资，情况需要核实，能先帮我梳理吗？另外还涉及工伤。

```json
{
  "claims_gold": [
    "labor_double_pay",
    "labor_work_injury"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求支付二倍工资",
    "contract_signed": "已签书面合同",
    "demand_contract": "提出过",
    "disability_level": "十级",
    "employer": "青禾技术有限公司",
    "injury_at_work": "工作时间和场所内",
    "injury_date": "2026-02-01",
    "injury_evidence": "医院病历",
    "injury_recognized": "已认定工伤",
    "injury_reported": "单位30日内申请",
    "medical_cost": 12000,
    "monthly_wage": 10000,
    "no_contract_months": 5,
    "start_date": "2021-03-01",
    "work_injury_insurance": "参加了工伤保险"
  },
  "critical": [
    "contract_signed",
    "disability_level",
    "injury_at_work",
    "injury_date",
    "injury_recognized",
    "injury_reported",
    "monthly_wage",
    "start_date",
    "work_injury_insurance"
  ],
  "gold_before": [
    {
      "claim": "labor_double_pay",
      "path": "finding:F_DP_NONE",
      "calculator": "literal",
      "depends": [
        "contract_signed"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_work_injury",
      "path": "calculation.amount",
      "calculator": "work_injury",
      "depends": [
        "monthly_wage",
        "disability_level"
      ],
      "expected": 70000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_double_pay",
      "path": "finding:F_DP_NONE",
      "calculator": "literal",
      "depends": [
        "contract_signed"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_work_injury",
      "path": "calculation.amount",
      "calculator": "work_injury",
      "depends": [
        "monthly_wage",
        "disability_level"
      ],
      "expected": 70000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B13 · labor_work_injury · dev

我想咨询工伤认定和伤残待遇，要先准备什么？

```json
{
  "claims_gold": [
    "labor_work_injury"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求工伤待遇",
    "disability_level": "十级",
    "employer": "青禾技术有限公司",
    "injury_at_work": "工作时间和场所内",
    "injury_date": "2026-02-01",
    "injury_evidence": "医院病历",
    "injury_recognized": "已认定工伤",
    "injury_reported": "单位30日内申请",
    "medical_cost": 12000,
    "monthly_wage": 10000,
    "start_date": "2021-03-01",
    "work_injury_insurance": "参加了工伤保险"
  },
  "critical": [
    "disability_level",
    "injury_at_work",
    "injury_date",
    "injury_recognized",
    "injury_reported",
    "monthly_wage",
    "start_date",
    "work_injury_insurance"
  ],
  "gold_before": [
    {
      "claim": "labor_work_injury",
      "path": "calculation.amount",
      "calculator": "work_injury",
      "depends": [
        "monthly_wage",
        "disability_level"
      ],
      "expected": 70000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_work_injury",
      "path": "calculation.amount",
      "calculator": "work_injury",
      "depends": [
        "monthly_wage",
        "disability_level"
      ],
      "expected": 70000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B14 · labor_work_injury · test

我想咨询工伤认定和伤残待遇，要先准备什么？

```json
{
  "claims_gold": [
    "labor_work_injury"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求工伤待遇",
    "disability_level": "十级",
    "employer": "青禾技术有限公司",
    "injury_at_work": "工作时间和场所内",
    "injury_date": "2026-02-01",
    "injury_evidence": "医院病历",
    "injury_recognized": "已认定工伤",
    "injury_reported": "单位30日内申请",
    "medical_cost": 12000,
    "monthly_wage": 12000,
    "start_date": "2020-04-01",
    "work_injury_insurance": "参加了工伤保险"
  },
  "critical": [
    "disability_level",
    "injury_at_work",
    "injury_date",
    "injury_recognized",
    "injury_reported",
    "monthly_wage",
    "start_date",
    "work_injury_insurance"
  ],
  "gold_before": [
    {
      "claim": "labor_work_injury",
      "path": "calculation.amount",
      "calculator": "work_injury",
      "depends": [
        "monthly_wage",
        "disability_level"
      ],
      "expected": 84000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_work_injury",
      "path": "calculation.amount",
      "calculator": "work_injury",
      "depends": [
        "monthly_wage",
        "disability_level"
      ],
      "expected": 108000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "disability_level", "old": "十级", "new": "九级", "text": "更正一下，我之前说错了。关于伤残等级，九级。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B15 · labor_work_injury · test

我想咨询工伤，情况需要核实，能先帮我梳理吗？另外还涉及社保/公积金。

```json
{
  "claims_gold": [
    "labor_work_injury",
    "labor_social_insurance"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求工伤待遇",
    "disability_level": "十级",
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "housing_fund": "正常缴纳",
    "injury_at_work": "因工外出",
    "injury_date": "2026-02-01",
    "injury_evidence": "医院病历",
    "injury_recognized": "已认定工伤",
    "injury_reported": "单位30日内申请",
    "medical_cost": 12000,
    "monthly_wage": 10000,
    "social_insurance": "未缴纳",
    "social_insurance_claim": "要求补缴",
    "social_insurance_gap": "2026年1月至2月",
    "social_insurance_years": 5,
    "start_date": "2021-03-01",
    "work_injury_insurance": "没有参加"
  },
  "critical": [
    "disability_level",
    "injury_at_work",
    "injury_date",
    "injury_recognized",
    "injury_reported",
    "monthly_wage",
    "social_insurance",
    "social_insurance_claim",
    "social_insurance_gap",
    "start_date",
    "work_injury_insurance"
  ],
  "gold_before": [
    {
      "claim": "labor_work_injury",
      "path": "calculation.amount",
      "calculator": "work_injury",
      "depends": [
        "monthly_wage",
        "disability_level"
      ],
      "expected": 70000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_social_insurance",
      "path": "finding:F_SI_FORCED",
      "calculator": "condition",
      "depends": [
        "social_insurance_claim"
      ],
      "conditions": {
        "social_insurance_claim": "要求被迫解除经济补偿"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_work_injury",
      "path": "calculation.amount",
      "calculator": "work_injury",
      "depends": [
        "monthly_wage",
        "disability_level"
      ],
      "expected": 70000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_social_insurance",
      "path": "finding:F_SI_FORCED",
      "calculator": "condition",
      "depends": [
        "social_insurance_claim"
      ],
      "conditions": {
        "social_insurance_claim": "要求被迫解除经济补偿"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B16 · labor_social_insurance · dev

公司没交社保，我想问补缴的事情。

```json
{
  "claims_gold": [
    "labor_social_insurance"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "housing_fund": "正常缴纳",
    "monthly_wage": 10000,
    "social_insurance": "未缴纳",
    "social_insurance_claim": "要求补缴",
    "social_insurance_gap": "2026年1月至2月",
    "social_insurance_years": 5,
    "start_date": "2021-03-01"
  },
  "critical": [
    "monthly_wage",
    "social_insurance",
    "social_insurance_claim",
    "social_insurance_gap",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_social_insurance",
      "path": "finding:F_SI_FORCED",
      "calculator": "condition",
      "depends": [
        "social_insurance_claim"
      ],
      "conditions": {
        "social_insurance_claim": "要求被迫解除经济补偿"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_social_insurance",
      "path": "finding:F_SI_FORCED",
      "calculator": "condition",
      "depends": [
        "social_insurance_claim"
      ],
      "conditions": {
        "social_insurance_claim": "要求被迫解除经济补偿"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B17 · labor_social_insurance · test

公司没交社保，我想问补缴的事情。

```json
{
  "claims_gold": [
    "labor_social_insurance"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "housing_fund": "正常缴纳",
    "monthly_wage": 12000,
    "social_insurance": "未缴纳",
    "social_insurance_claim": "要求补缴",
    "social_insurance_gap": "2026年1月至2月",
    "social_insurance_years": 5,
    "start_date": "2020-04-01"
  },
  "critical": [
    "monthly_wage",
    "social_insurance",
    "social_insurance_claim",
    "social_insurance_gap",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_social_insurance",
      "path": "finding:F_SI_FORCED",
      "calculator": "condition",
      "depends": [
        "social_insurance_claim"
      ],
      "conditions": {
        "social_insurance_claim": "要求被迫解除经济补偿"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_social_insurance",
      "path": "finding:F_SI_FORCED",
      "calculator": "condition",
      "depends": [
        "social_insurance_claim"
      ],
      "conditions": {
        "social_insurance_claim": "要求被迫解除经济补偿"
      },
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "social_insurance_claim", "old": "要求补缴", "new": "要求被迫解除经济补偿", "text": "更正一下，我之前说错了。关于社保诉求，要求被迫解除经济补偿。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B18 · labor_social_insurance · test

我想咨询社保/公积金，情况需要核实，能先帮我梳理吗？另外还涉及年休假。

```json
{
  "claims_gold": [
    "labor_social_insurance",
    "labor_annual_leave"
  ],
  "hidden": {
    "annual_leave_paid": "没有支付",
    "annual_leave_taken": 2,
    "annual_leave_year": "2025",
    "arbitration_filed": "已申请",
    "cumulative_work_years": 9,
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "housing_fund": "正常缴纳",
    "monthly_wage": 10000,
    "social_insurance": "正常缴纳",
    "social_insurance_claim": "要求补缴",
    "social_insurance_gap": "2026年1月至2月",
    "social_insurance_years": 5,
    "start_date": "2021-03-01"
  },
  "critical": [
    "annual_leave_paid",
    "annual_leave_taken",
    "annual_leave_year",
    "cumulative_work_years",
    "monthly_wage",
    "social_insurance",
    "social_insurance_claim",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_social_insurance",
      "path": "finding:F_SI_FORCED",
      "calculator": "condition",
      "depends": [
        "social_insurance_claim"
      ],
      "conditions": {
        "social_insurance_claim": "要求被迫解除经济补偿"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_annual_leave",
      "path": "calculation.amount",
      "calculator": "annual_leave",
      "depends": [
        "monthly_wage",
        "cumulative_work_years",
        "annual_leave_taken"
      ],
      "expected": 2758.62,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_social_insurance",
      "path": "finding:F_SI_FORCED",
      "calculator": "condition",
      "depends": [
        "social_insurance_claim"
      ],
      "conditions": {
        "social_insurance_claim": "要求被迫解除经济补偿"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_annual_leave",
      "path": "calculation.amount",
      "calculator": "annual_leave",
      "depends": [
        "monthly_wage",
        "cumulative_work_years",
        "annual_leave_taken"
      ],
      "expected": 2758.62,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B19 · labor_annual_leave · dev

我有未休年假，想问年假工资怎么计算。

```json
{
  "claims_gold": [
    "labor_annual_leave"
  ],
  "hidden": {
    "annual_leave_paid": "没有支付",
    "annual_leave_taken": 2,
    "annual_leave_year": "2025",
    "arbitration_filed": "已申请",
    "cumulative_work_years": 9,
    "monthly_wage": 10000,
    "start_date": "2021-03-01"
  },
  "critical": [
    "annual_leave_paid",
    "annual_leave_taken",
    "annual_leave_year",
    "cumulative_work_years",
    "monthly_wage",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_annual_leave",
      "path": "calculation.amount",
      "calculator": "annual_leave",
      "depends": [
        "monthly_wage",
        "cumulative_work_years",
        "annual_leave_taken"
      ],
      "expected": 2758.62,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_annual_leave",
      "path": "calculation.amount",
      "calculator": "annual_leave",
      "depends": [
        "monthly_wage",
        "cumulative_work_years",
        "annual_leave_taken"
      ],
      "expected": 2758.62,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B20 · labor_annual_leave · test

我有未休年假，想问年假工资怎么计算。

```json
{
  "claims_gold": [
    "labor_annual_leave"
  ],
  "hidden": {
    "annual_leave_paid": "没有支付",
    "annual_leave_taken": 2,
    "annual_leave_year": "2025",
    "arbitration_filed": "已申请",
    "cumulative_work_years": 9,
    "monthly_wage": 12000,
    "start_date": "2020-04-01"
  },
  "critical": [
    "annual_leave_paid",
    "annual_leave_taken",
    "annual_leave_year",
    "cumulative_work_years",
    "monthly_wage",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_annual_leave",
      "path": "calculation.amount",
      "calculator": "annual_leave",
      "depends": [
        "monthly_wage",
        "cumulative_work_years",
        "annual_leave_taken"
      ],
      "expected": 3310.34,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_annual_leave",
      "path": "calculation.amount",
      "calculator": "annual_leave",
      "depends": [
        "monthly_wage",
        "cumulative_work_years",
        "annual_leave_taken"
      ],
      "expected": 8827.59,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "cumulative_work_years", "old": 9, "new": 10, "text": "更正一下，我之前说错了。累计工作10年。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B21 · labor_annual_leave · test

我想咨询年休假，情况需要核实，能先帮我梳理吗？另外还涉及竞业限制。

```json
{
  "claims_gold": [
    "labor_annual_leave",
    "labor_noncompete"
  ],
  "hidden": {
    "annual_leave_paid": "没有支付",
    "annual_leave_taken": 2,
    "annual_leave_year": "2025",
    "arbitration_filed": "已申请",
    "cumulative_work_years": 20,
    "dismiss_date": "2026-03-15",
    "monthly_wage": null,
    "new_employer_competitor": "没有去",
    "noncompete_claim": "要求支付补偿",
    "noncompete_compensation": 4000,
    "noncompete_months": 12,
    "noncompete_paid": "没有支付",
    "noncompete_signed": "签了竞业限制协议",
    "start_date": "2021-03-01"
  },
  "critical": [
    "annual_leave_paid",
    "annual_leave_taken",
    "annual_leave_year",
    "cumulative_work_years",
    "dismiss_date",
    "monthly_wage",
    "new_employer_competitor",
    "noncompete_claim",
    "noncompete_compensation",
    "noncompete_months",
    "noncompete_paid",
    "noncompete_signed",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_annual_leave",
      "path": "calculation.amount",
      "calculator": "annual_leave",
      "depends": [
        "monthly_wage",
        "cumulative_work_years",
        "annual_leave_taken"
      ],
      "expected": null,
      "applicable": false,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_noncompete",
      "path": "calculation.amount",
      "calculator": "noncompete",
      "depends": [
        "noncompete_months",
        "noncompete_compensation"
      ],
      "expected": 48000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_annual_leave",
      "path": "calculation.amount",
      "calculator": "annual_leave",
      "depends": [
        "monthly_wage",
        "cumulative_work_years",
        "annual_leave_taken"
      ],
      "expected": null,
      "applicable": false,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_noncompete",
      "path": "calculation.amount",
      "calculator": "noncompete",
      "depends": [
        "noncompete_months",
        "noncompete_compensation"
      ],
      "expected": 48000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B22 · labor_noncompete · dev

签了竞业限制协议，公司没有支付竞业补偿。

```json
{
  "claims_gold": [
    "labor_noncompete"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "dismiss_date": "2026-03-15",
    "monthly_wage": 10000,
    "new_employer_competitor": "没有去",
    "noncompete_claim": "要求支付补偿",
    "noncompete_compensation": 4000,
    "noncompete_months": 12,
    "noncompete_paid": "没有支付",
    "noncompete_signed": "签了竞业限制协议"
  },
  "critical": [
    "dismiss_date",
    "monthly_wage",
    "new_employer_competitor",
    "noncompete_claim",
    "noncompete_compensation",
    "noncompete_months",
    "noncompete_paid",
    "noncompete_signed"
  ],
  "gold_before": [
    {
      "claim": "labor_noncompete",
      "path": "calculation.amount",
      "calculator": "noncompete",
      "depends": [
        "noncompete_months",
        "noncompete_compensation"
      ],
      "expected": 48000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_noncompete",
      "path": "calculation.amount",
      "calculator": "noncompete",
      "depends": [
        "noncompete_months",
        "noncompete_compensation"
      ],
      "expected": 48000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B23 · labor_noncompete · test

签了竞业限制协议，公司没有支付竞业补偿。

```json
{
  "claims_gold": [
    "labor_noncompete"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "dismiss_date": "2026-03-15",
    "monthly_wage": 12000,
    "new_employer_competitor": "没有去",
    "noncompete_claim": "要求支付补偿",
    "noncompete_compensation": 4000,
    "noncompete_months": 12,
    "noncompete_paid": "没有支付",
    "noncompete_signed": "签了竞业限制协议"
  },
  "critical": [
    "dismiss_date",
    "monthly_wage",
    "new_employer_competitor",
    "noncompete_claim",
    "noncompete_compensation",
    "noncompete_months",
    "noncompete_paid",
    "noncompete_signed"
  ],
  "gold_before": [
    {
      "claim": "labor_noncompete",
      "path": "calculation.amount",
      "calculator": "noncompete",
      "depends": [
        "noncompete_months",
        "noncompete_compensation"
      ],
      "expected": 48000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_noncompete",
      "path": "calculation.amount",
      "calculator": "noncompete",
      "depends": [
        "noncompete_months",
        "noncompete_compensation"
      ],
      "expected": 72000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "noncompete_months", "old": 12, "new": 18, "text": "更正一下，我之前说错了。竞业限制期限是18个月。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B24 · labor_noncompete · test

我想咨询竞业限制，情况需要核实，能先帮我梳理吗？另外还涉及三期/生育。

```json
{
  "claims_gold": [
    "labor_noncompete",
    "labor_maternity"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "dismiss_date": "2026-03-15",
    "maternity_allowance": "单位发工资",
    "maternity_dismissal": "被降薪或调岗",
    "maternity_leave_taken": "还没休",
    "monthly_wage": null,
    "new_employer_competitor": "没有去",
    "noncompete_claim": "要求支付补偿",
    "noncompete_compensation": 0,
    "noncompete_months": 0,
    "noncompete_paid": "没有支付",
    "noncompete_signed": "没有签",
    "pregnancy_status": "孕期",
    "social_insurance": "未缴纳"
  },
  "critical": [
    "dismiss_date",
    "maternity_allowance",
    "maternity_dismissal",
    "maternity_leave_taken",
    "monthly_wage",
    "noncompete_signed",
    "pregnancy_status"
  ],
  "gold_before": [
    {
      "claim": "labor_noncompete",
      "path": "finding:F_NC_NONE",
      "calculator": "literal",
      "depends": [
        "noncompete_signed"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_maternity",
      "path": "finding:F_MT_DISMISS",
      "calculator": "condition",
      "depends": [
        "maternity_dismissal"
      ],
      "conditions": {
        "maternity_dismissal": "因怀孕/生育被辞退"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_noncompete",
      "path": "finding:F_NC_NONE",
      "calculator": "literal",
      "depends": [
        "noncompete_signed"
      ],
      "value": true,
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_maternity",
      "path": "finding:F_MT_DISMISS",
      "calculator": "condition",
      "depends": [
        "maternity_dismissal"
      ],
      "conditions": {
        "maternity_dismissal": "因怀孕/生育被辞退"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B25 · labor_maternity · dev

我在孕期，公司降低了工资待遇，想了解生育保护。

```json
{
  "claims_gold": [
    "labor_maternity"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "dismiss_date": "2026-03-15",
    "maternity_allowance": "单位发工资",
    "maternity_dismissal": "被降薪或调岗",
    "maternity_leave_taken": "还没休",
    "monthly_wage": 10000,
    "pregnancy_status": "孕期",
    "social_insurance": "未缴纳"
  },
  "critical": [
    "dismiss_date",
    "maternity_allowance",
    "maternity_dismissal",
    "maternity_leave_taken",
    "monthly_wage",
    "pregnancy_status"
  ],
  "gold_before": [
    {
      "claim": "labor_maternity",
      "path": "finding:F_MT_DISMISS",
      "calculator": "condition",
      "depends": [
        "maternity_dismissal"
      ],
      "conditions": {
        "maternity_dismissal": "因怀孕/生育被辞退"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_maternity",
      "path": "finding:F_MT_DISMISS",
      "calculator": "condition",
      "depends": [
        "maternity_dismissal"
      ],
      "conditions": {
        "maternity_dismissal": "因怀孕/生育被辞退"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B26 · labor_maternity · test

我在孕期，公司降低了工资待遇，想了解生育保护。

```json
{
  "claims_gold": [
    "labor_maternity"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "dismiss_date": "2026-03-15",
    "maternity_allowance": "单位发工资",
    "maternity_dismissal": "被降薪或调岗",
    "maternity_leave_taken": "还没休",
    "monthly_wage": 12000,
    "pregnancy_status": "孕期",
    "social_insurance": "未缴纳"
  },
  "critical": [
    "dismiss_date",
    "maternity_allowance",
    "maternity_dismissal",
    "maternity_leave_taken",
    "monthly_wage",
    "pregnancy_status"
  ],
  "gold_before": [
    {
      "claim": "labor_maternity",
      "path": "finding:F_MT_DISMISS",
      "calculator": "condition",
      "depends": [
        "maternity_dismissal"
      ],
      "conditions": {
        "maternity_dismissal": "因怀孕/生育被辞退"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_maternity",
      "path": "finding:F_MT_DISMISS",
      "calculator": "condition",
      "depends": [
        "maternity_dismissal"
      ],
      "conditions": {
        "maternity_dismissal": "因怀孕/生育被辞退"
      },
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "maternity_dismissal", "old": "被降薪或调岗", "new": "因怀孕/生育被辞退", "text": "更正一下，我之前说错了。关于是否因三期被辞退，因怀孕/生育被辞退。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B27 · labor_maternity · test

我想咨询三期/生育，情况需要核实，能先帮我梳理吗？

```json
{
  "claims_gold": [
    "labor_maternity"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "dismiss_date": "2026-03-15",
    "maternity_allowance": null,
    "maternity_dismissal": "被降薪或调岗",
    "maternity_leave_taken": "还没休",
    "monthly_wage": 10000,
    "pregnancy_status": "哺乳期",
    "social_insurance": "未缴纳"
  },
  "critical": [
    "dismiss_date",
    "maternity_allowance",
    "maternity_dismissal",
    "maternity_leave_taken",
    "monthly_wage",
    "pregnancy_status"
  ],
  "gold_before": [
    {
      "claim": "labor_maternity",
      "path": "finding:F_MT_DISMISS",
      "calculator": "condition",
      "depends": [
        "maternity_dismissal"
      ],
      "conditions": {
        "maternity_dismissal": "因怀孕/生育被辞退"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_maternity",
      "path": "finding:F_MT_DISMISS",
      "calculator": "condition",
      "depends": [
        "maternity_dismissal"
      ],
      "conditions": {
        "maternity_dismissal": "因怀孕/生育被辞退"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B28 · labor_dispatch · dev

我是劳务派遣员工，想确认劳动关系和责任单位。

```json
{
  "claims_gold": [
    "labor_dispatch"
  ],
  "hidden": {
    "actual_employer": "远帆制造有限公司",
    "arbitration_filed": "已申请",
    "claim_type": "要求确认劳动关系",
    "dispatch_type": "劳务派遣",
    "employer": "青禾技术有限公司",
    "monthly_wage": 10000,
    "pay_by": "青禾技术有限公司",
    "platform_worker": "不是",
    "social_insurance": "未缴纳",
    "start_date": "2021-03-01",
    "uniform_tools": "穿工服/用公司工具",
    "work_management": "打卡考勤"
  },
  "critical": [
    "actual_employer",
    "claim_type",
    "dispatch_type",
    "employer",
    "monthly_wage",
    "pay_by",
    "start_date",
    "work_management"
  ],
  "gold_before": [
    {
      "claim": "labor_dispatch",
      "path": "finding_text:F_DP_FORM",
      "calculator": "fact",
      "depends": [
        "dispatch_type"
      ],
      "field": "dispatch_type",
      "match": "contains",
      "expected": "劳务派遣",
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_dispatch",
      "path": "finding_text:F_DP_FORM",
      "calculator": "fact",
      "depends": [
        "dispatch_type"
      ],
      "field": "dispatch_type",
      "match": "contains",
      "expected": "劳务派遣",
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B29 · labor_dispatch · test

我是劳务派遣员工，想确认劳动关系和责任单位。

```json
{
  "claims_gold": [
    "labor_dispatch"
  ],
  "hidden": {
    "actual_employer": "远帆制造有限公司",
    "arbitration_filed": "已申请",
    "claim_type": "要求确认劳动关系",
    "dispatch_type": "劳务派遣",
    "employer": "青禾技术有限公司",
    "monthly_wage": 12000,
    "pay_by": "青禾技术有限公司",
    "platform_worker": "不是",
    "social_insurance": "未缴纳",
    "start_date": "2020-04-01",
    "uniform_tools": "穿工服/用公司工具",
    "work_management": "打卡考勤"
  },
  "critical": [
    "actual_employer",
    "claim_type",
    "dispatch_type",
    "employer",
    "monthly_wage",
    "pay_by",
    "start_date",
    "work_management"
  ],
  "gold_before": [
    {
      "claim": "labor_dispatch",
      "path": "finding_text:F_DP_FORM",
      "calculator": "fact",
      "depends": [
        "dispatch_type"
      ],
      "field": "dispatch_type",
      "match": "contains",
      "expected": "劳务派遣",
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_dispatch",
      "path": "finding_text:F_DP_FORM",
      "calculator": "fact",
      "depends": [
        "dispatch_type"
      ],
      "field": "dispatch_type",
      "match": "contains",
      "expected": "业务外包",
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "dispatch_type", "old": "劳务派遣", "new": "业务外包", "text": "更正一下，我之前说错了。关于用工形式，业务外包。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B30 · labor_dispatch · test

我想咨询派遣/外包/新业态，情况需要核实，能先帮我梳理吗？

```json
{
  "claims_gold": [
    "labor_dispatch"
  ],
  "hidden": {
    "actual_employer": null,
    "arbitration_filed": "已申请",
    "claim_type": "要求确认劳动关系",
    "dispatch_type": "平台/新业态用工",
    "employer": "青禾技术有限公司",
    "monthly_wage": 10000,
    "pay_by": "青禾技术有限公司",
    "platform_worker": "外卖骑手",
    "social_insurance": "未缴纳",
    "start_date": "2021-03-01",
    "uniform_tools": "穿工服/用公司工具",
    "work_management": "打卡考勤"
  },
  "critical": [
    "actual_employer",
    "claim_type",
    "dispatch_type",
    "employer",
    "monthly_wage",
    "pay_by",
    "start_date",
    "work_management"
  ],
  "gold_before": [
    {
      "claim": "labor_dispatch",
      "path": "finding_text:F_DP_FORM",
      "calculator": "fact",
      "depends": [
        "dispatch_type"
      ],
      "field": "dispatch_type",
      "match": "contains",
      "expected": "平台/新业态用工",
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_dispatch",
      "path": "finding_text:F_DP_FORM",
      "calculator": "fact",
      "depends": [
        "dispatch_type"
      ],
      "field": "dispatch_type",
      "match": "contains",
      "expected": "平台/新业态用工",
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B31 · labor_contract · dev

我想咨询试用期和劳动合同变更。

```json
{
  "claims_gold": [
    "labor_contract"
  ],
  "hidden": {
    "claim_type": "还没想好",
    "contract_copies": "我有一份",
    "contract_signed": "已签书面合同",
    "contract_terms_changed": "没有",
    "contract_type": "固定期限",
    "illegal_probation": "没有",
    "monthly_wage": 10000,
    "probation": "有试用期",
    "probation_length": 2,
    "probation_wage": 8500,
    "start_date": "2021-03-01"
  },
  "critical": [
    "claim_type",
    "contract_signed",
    "contract_terms_changed",
    "contract_type",
    "illegal_probation",
    "monthly_wage",
    "probation",
    "probation_length",
    "probation_wage",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_contract",
      "path": "finding:F_CT_CHANGE",
      "calculator": "condition",
      "depends": [
        "contract_terms_changed"
      ],
      "conditions": {
        "contract_terms_changed": "被单方变更"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_contract",
      "path": "finding:F_CT_CHANGE",
      "calculator": "condition",
      "depends": [
        "contract_terms_changed"
      ],
      "conditions": {
        "contract_terms_changed": "被单方变更"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B32 · labor_contract · test

我想咨询试用期和劳动合同变更。

```json
{
  "claims_gold": [
    "labor_contract"
  ],
  "hidden": {
    "claim_type": "还没想好",
    "contract_copies": "我有一份",
    "contract_signed": "已签书面合同",
    "contract_terms_changed": "没有",
    "contract_type": "固定期限",
    "illegal_probation": "没有",
    "monthly_wage": 12000,
    "probation": "有试用期",
    "probation_length": 2,
    "probation_wage": 8500,
    "start_date": "2020-04-01"
  },
  "critical": [
    "claim_type",
    "contract_signed",
    "contract_terms_changed",
    "contract_type",
    "illegal_probation",
    "monthly_wage",
    "probation",
    "probation_length",
    "probation_wage",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_contract",
      "path": "finding:F_CT_CHANGE",
      "calculator": "condition",
      "depends": [
        "contract_terms_changed"
      ],
      "conditions": {
        "contract_terms_changed": "被单方变更"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_contract",
      "path": "finding:F_CT_CHANGE",
      "calculator": "condition",
      "depends": [
        "contract_terms_changed"
      ],
      "conditions": {
        "contract_terms_changed": "被单方变更"
      },
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "contract_terms_changed", "old": "没有", "new": "被单方变更", "text": "更正一下，我之前说错了。关于合同是否被单方变更，被单方变更。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B33 · labor_contract · test

我想咨询合同订立/试用期/变更，情况需要核实，能先帮我梳理吗？

```json
{
  "claims_gold": [
    "labor_contract"
  ],
  "hidden": {
    "claim_type": "还没想好",
    "contract_copies": "我有一份",
    "contract_signed": "已签书面合同",
    "contract_terms_changed": "没有",
    "contract_type": null,
    "illegal_probation": "没有",
    "monthly_wage": 10000,
    "probation": "没有试用期",
    "probation_length": 0,
    "probation_wage": 0,
    "start_date": "2021-03-01"
  },
  "critical": [
    "claim_type",
    "contract_signed",
    "contract_terms_changed",
    "contract_type",
    "monthly_wage",
    "probation",
    "start_date"
  ],
  "gold_before": [
    {
      "claim": "labor_contract",
      "path": "finding:F_CT_CHANGE",
      "calculator": "condition",
      "depends": [
        "contract_terms_changed"
      ],
      "conditions": {
        "contract_terms_changed": "被单方变更"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_contract",
      "path": "finding:F_CT_CHANGE",
      "calculator": "condition",
      "depends": [
        "contract_terms_changed"
      ],
      "conditions": {
        "contract_terms_changed": "被单方变更"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B34 · labor_procedure · dev

我已经申请劳动仲裁，想了解后续程序。

```json
{
  "claims_gold": [
    "labor_procedure"
  ],
  "hidden": {
    "amount_in_dispute": 20000,
    "arbitration_date": "2026-04-10",
    "arbitration_filed": "已申请",
    "arbitration_result": "已受理",
    "claim_type": "要求赔偿金",
    "court_filed": "没有起诉",
    "deadline_aware": "知道，还没过",
    "employer": "青禾技术有限公司",
    "work_location": "上海"
  },
  "critical": [
    "amount_in_dispute",
    "arbitration_date",
    "arbitration_filed",
    "arbitration_result",
    "claim_type",
    "court_filed",
    "deadline_aware"
  ],
  "gold_before": [
    {
      "claim": "labor_procedure",
      "path": "gap_contains:已裁决的案件需核对",
      "calculator": "condition",
      "depends": [
        "arbitration_filed",
        "arbitration_result"
      ],
      "conditions": {
        "arbitration_filed": "已申请",
        "arbitration_result": "已裁决"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_procedure",
      "path": "gap_contains:已裁决的案件需核对",
      "calculator": "condition",
      "depends": [
        "arbitration_filed",
        "arbitration_result"
      ],
      "conditions": {
        "arbitration_filed": "已申请",
        "arbitration_result": "已裁决"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B35 · labor_procedure · test

我已经申请劳动仲裁，想了解后续程序。

```json
{
  "claims_gold": [
    "labor_procedure"
  ],
  "hidden": {
    "amount_in_dispute": 24000,
    "arbitration_date": "2026-05-10",
    "arbitration_filed": "已申请",
    "arbitration_result": "已受理",
    "claim_type": "要求赔偿金",
    "court_filed": "没有起诉",
    "deadline_aware": "知道，还没过",
    "employer": "青禾技术有限公司",
    "work_location": "上海"
  },
  "critical": [
    "amount_in_dispute",
    "arbitration_date",
    "arbitration_filed",
    "arbitration_result",
    "claim_type",
    "court_filed",
    "deadline_aware"
  ],
  "gold_before": [
    {
      "claim": "labor_procedure",
      "path": "gap_contains:已裁决的案件需核对",
      "calculator": "condition",
      "depends": [
        "arbitration_filed",
        "arbitration_result"
      ],
      "conditions": {
        "arbitration_filed": "已申请",
        "arbitration_result": "已裁决"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_procedure",
      "path": "gap_contains:已裁决的案件需核对",
      "calculator": "condition",
      "depends": [
        "arbitration_filed",
        "arbitration_result"
      ],
      "conditions": {
        "arbitration_filed": "已申请",
        "arbitration_result": "已裁决"
      },
      "expected": true,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：{"after": "first_memo", "key": "arbitration_result", "old": "已受理", "new": "已裁决", "text": "更正一下，我之前说错了。关于仲裁进展，已裁决。"}

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B36 · labor_procedure · test

我想咨询劳动仲裁和后续劳动诉讼的程序，情况需要核实，能先帮我梳理吗？

```json
{
  "claims_gold": [
    "labor_procedure"
  ],
  "hidden": {
    "amount_in_dispute": 20000,
    "arbitration_date": null,
    "arbitration_filed": "已申请",
    "arbitration_result": "已受理",
    "claim_type": "要求赔偿金",
    "court_filed": "没有起诉",
    "deadline_aware": "知道，还没过",
    "employer": "青禾技术有限公司",
    "work_location": "上海"
  },
  "critical": [
    "amount_in_dispute",
    "arbitration_date",
    "arbitration_filed",
    "arbitration_result",
    "claim_type",
    "court_filed",
    "deadline_aware"
  ],
  "gold_before": [
    {
      "claim": "labor_procedure",
      "path": "gap_contains:已裁决的案件需核对",
      "calculator": "condition",
      "depends": [
        "arbitration_filed",
        "arbitration_result"
      ],
      "conditions": {
        "arbitration_filed": "已申请",
        "arbitration_result": "已裁决"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_procedure",
      "path": "gap_contains:已裁决的案件需核对",
      "calculator": "condition",
      "depends": [
        "arbitration_filed",
        "arbitration_result"
      ],
      "conditions": {
        "arbitration_filed": "已申请",
        "arbitration_result": "已裁决"
      },
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B37 · labor_dismissal · test

我自己辞职，想问解除劳动合同后还有经济补偿吗？

```json
{
  "claims_gold": [
    "labor_dismissal"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求赔偿金",
    "compensation_paid": "未支付任何补偿",
    "contract_expired": "合同期内解除",
    "contract_signed": "已签书面合同",
    "deadline_aware": "知道，还没过",
    "dismiss_date": "2026-03-15",
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "misconduct_proof": "只有口头指认",
    "monthly_wage": 10000,
    "notice_30d": "都没有",
    "pregnancy_status": "不是",
    "rule_democratic": "没有经过",
    "rule_exists": "有成文制度",
    "rule_publicized": "没有公示告知",
    "start_date": "2021-03-01",
    "stated_reason": "其他或说不清",
    "training_or_transfer": "没有",
    "union_notified": "没有通知",
    "who_initiated": "劳动者辞职"
  },
  "critical": [
    "claim_type",
    "contract_signed",
    "dismiss_date",
    "employer",
    "forced_resignation_reason",
    "monthly_wage",
    "start_date",
    "stated_reason",
    "who_initiated"
  ],
  "gold_before": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "who_initiated",
        "stated_reason"
      ],
      "value": false,
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "0",
      "expected": 0.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "who_initiated",
        "stated_reason"
      ],
      "value": false,
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "0",
      "expected": 0.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

## B38 · labor_dismissal · test

劳动合同到期，公司不续签，经济补偿应该怎么算？

```json
{
  "claims_gold": [
    "labor_dismissal"
  ],
  "hidden": {
    "arbitration_filed": "已申请",
    "claim_type": "要求赔偿金",
    "compensation_paid": "未支付任何补偿",
    "contract_expired": "合同到期不续签",
    "contract_signed": "已签书面合同",
    "deadline_aware": "知道，还没过",
    "dismiss_date": "2026-03-15",
    "employer": "青禾技术有限公司",
    "forced_resignation_reason": "不适用",
    "misconduct_proof": "只有口头指认",
    "monthly_wage": 10000,
    "notice_30d": "都没有",
    "pregnancy_status": "不是",
    "rule_democratic": "没有经过",
    "rule_exists": "有成文制度",
    "rule_publicized": "没有公示告知",
    "start_date": "2021-03-01",
    "stated_reason": "合同期满不续签",
    "training_or_transfer": "没有",
    "union_notified": "没有通知",
    "who_initiated": "单位单方解除"
  },
  "critical": [
    "claim_type",
    "contract_expired",
    "contract_signed",
    "dismiss_date",
    "employer",
    "monthly_wage",
    "start_date",
    "stated_reason",
    "union_notified",
    "who_initiated"
  ],
  "gold_before": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "who_initiated",
        "stated_reason"
      ],
      "value": false,
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "N",
      "expected": 55000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "gold_after": [
    {
      "claim": "labor_dismissal",
      "path": "illegal",
      "calculator": "literal",
      "depends": [
        "who_initiated",
        "stated_reason"
      ],
      "value": false,
      "expected": false,
      "applicable": true,
      "reference_kind": "author_specified_behavior"
    },
    {
      "claim": "labor_dismissal",
      "path": "compensation.amount",
      "calculator": "dismissal",
      "depends": [
        "start_date",
        "dismiss_date",
        "monthly_wage"
      ],
      "pay_type": "N",
      "expected": 55000.0,
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.deadline",
      "calculator": "deadline",
      "depends": [
        "dismiss_date"
      ],
      "expected": "2027-03-15",
      "applicable": true,
      "reference_kind": "independent_formula"
    },
    {
      "claim": "labor_dismissal",
      "path": "limitation.expired",
      "calculator": "expired",
      "depends": [
        "dismiss_date"
      ],
      "expected": false,
      "applicable": true,
      "reference_kind": "independent_formula"
    }
  ],
  "assumptions": [
    "合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"
  ]
}
```

更正：null

依据：https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_0abfdd261c03417b949df19d869add8d.html-0；https://www.court.gov.cn/zixun/xiangqing/282121.html；https://xzfg.moj.gov.cn/front/law/detail?LawID=208；https://www.mohrss.gov.cn/xxgk2020/gzk/gz/202112/P020211229590352867273.pdf；https://xzfg.moj.gov.cn/mobile/law/detail?LawID=610；https://flk.npc.gov.cn/

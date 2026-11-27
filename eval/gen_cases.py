#!/usr/bin/env python3
"""Build reproducible synthetic seeds; optional API surface rewrites are unreviewed.

The default corpus is curated/template-generated, never mislabelled AI-generated.
Gold is computed independently, and human legal review remains pending.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from case_seeds import COMMON, OVERRIDES, SEEDS, SOURCES, UNKNOWN_KEYS, answer_text
from reference_oracle import reference_gold


def matches(facts, cond):
    for key, expected in cond.items():
        if key.endswith("__in"):
            if facts.get(key[:-4]) not in expected:
                return False
        elif key.endswith("__not"):
            if facts.get(key[:-5]) == expected:
                return False
        elif facts.get(key) != expected:
            return False
    return True


def critical_keys(claims, facts, schema):
    result = set()
    for claim in claims:
        for field in schema["claims"][claim]["fields"]:
            conditions = field.get("critical_if")
            active = any(matches(facts, c) for c in conditions) if conditions else field.get("critical", False)
            if active:
                result.add(field["key"])
    return sorted(result)


def specs_for(claim, facts):
    def spec(path, calculator, depends=(), **kwargs):
        return {"claim": claim, "path": path, "calculator": calculator,
                "depends": list(depends), **kwargs}
    if claim == "labor_dismissal":
        # Explicit scenario label, NOT a second implementation of the legal classifier.
        return [spec("illegal", "literal", ("stated_reason", "rule_publicized"), value=True),
                spec("compensation.amount", "dismissal", ("start_date", "dismiss_date", "monthly_wage"), pay_type="2N"),
                spec("limitation.deadline", "deadline", ("dismiss_date",)),
                spec("limitation.expired", "expired", ("dismiss_date",))]
    if claim == "labor_wage":
        return [spec("finding_money:F_WAGE_AMOUNT", "fact", ("wage_owed",), field="wage_owed", tolerance=0.5)]
    if claim == "labor_overtime":
        if facts["overtime_exists"] == "没有":
            return [spec("finding:F_OT_NONE", "literal", ("overtime_exists",), value=True)]
        return [spec("calculation.amount", "overtime", ("monthly_wage", "overtime_hours_weekday", "overtime_hours_rest", "overtime_hours_holiday"))]
    if claim == "labor_double_pay":
        if facts["contract_signed"] == "已签书面合同":
            return [spec("finding:F_DP_NONE", "literal", ("contract_signed",), value=True)]
        return [spec("calculation.amount", "double_pay", ("monthly_wage", "no_contract_months"))]
    if claim == "labor_work_injury":
        return [spec("calculation.amount", "work_injury", ("monthly_wage", "disability_level"))]
    if claim == "labor_social_insurance":
        return [spec("finding:F_SI_FORCED", "condition", ("social_insurance_claim",),
                     conditions={"social_insurance_claim": "要求被迫解除经济补偿"})]
    if claim == "labor_annual_leave":
        return [spec("calculation.amount", "annual_leave", ("monthly_wage", "cumulative_work_years", "annual_leave_taken"))]
    if claim == "labor_noncompete":
        if facts["noncompete_signed"] == "没有签":
            return [spec("finding:F_NC_NONE", "literal", ("noncompete_signed",), value=True)]
        return [spec("calculation.amount", "noncompete", ("noncompete_months", "noncompete_compensation"))]
    if claim == "labor_maternity":
        return [spec("finding:F_MT_DISMISS", "condition", ("maternity_dismissal",),
                     conditions={"maternity_dismissal": "因怀孕/生育被辞退"})]
    if claim == "labor_dispatch":
        return [spec("finding_text:F_DP_FORM", "fact", ("dispatch_type",), field="dispatch_type", match="contains")]
    if claim == "labor_contract":
        return [spec("finding:F_CT_CHANGE", "condition", ("contract_terms_changed",),
                     conditions={"contract_terms_changed": "被单方变更"})]
    if claim == "labor_procedure":
        return [spec("gap_contains:已裁决的案件需核对", "condition", ("arbitration_filed", "arbitration_result"),
                     conditions={"arbitration_filed": "已申请", "arbitration_result": "已裁决"})]
    raise ValueError(claim)


def build_cases():
    schema = json.loads((ROOT / "data/elements.json").read_text())
    cases = []
    for index, (claim, opening, volunteered, correction, patch) in enumerate(SEEDS):
        for variant in range(3):
            claims = [claim]
            if variant == 2 and index < 8:
                claims.append(SEEDS[(index + 1) % 12][0])
            facts = copy.deepcopy(COMMON)
            for c in reversed(claims):
                facts.update(OVERRIDES.get(c, {}))
            opening_facts = dict(volunteered)
            text = opening
            if variant == 2:
                facts.update(patch)
                # Challenge statement describes its branch accurately; do not reuse the contradictory seed opening.
                text = f"我想咨询{schema['claims'][claim]['label'].split(' · ')[-1]}，情况需要核实，能先帮我梳理吗？"
                if claim == "labor_procedure":
                    text = "我想咨询劳动仲裁和后续劳动诉讼的程序，情况需要核实，能先帮我梳理吗？"
                opening_facts = {}
                if len(claims) > 1:
                    text += "另外还涉及" + schema["claims"][claims[1]]["label"].split(" · ")[-1] + "。"
                if claim in UNKNOWN_KEYS:
                    facts[UNKNOWN_KEYS[claim]] = None
            if variant == 1:
                facts["monthly_wage"] = 12000
                # Different employment facts from development; no identical substantive signature.
                facts["start_date"] = "2020-04-01"
                facts["wage_owed"] = 24000
                facts["overtime_hours_weekday"] = 24
                facts["amount_in_dispute"] = 24000
                facts["arbitration_date"] = "2026-05-10"
            if facts["overtime_exists"] == "没有":
                for key in ("overtime_hours_weekday", "overtime_hours_rest", "overtime_hours_holiday"):
                    facts[key] = 0
            if facts["noncompete_signed"] == "没有签":
                facts["noncompete_months"] = facts["noncompete_compensation"] = 0
            if facts["probation"] == "没有试用期":
                facts["probation_length"] = facts["probation_wage"] = 0
            keys = set()
            for c in claims:
                keys.update(f["key"] for f in schema["claims"][c]["fields"])
                for element in schema["claims"][c].get("elements", []):
                    keys.update(element.get("facts", []))
            hidden = {k: facts[k] for k in sorted(keys) if k in facts}
            # A disclosed value must agree with the seed, including when mixed claims share fields.
            opening_facts = {k: v for k, v in opening_facts.items() if k in hidden and hidden[k] == v}
            if variant == 2 and claim == "labor_dismissal":
                # Force a visible short-tenure independent-reference boundary.
                hidden["dismiss_date"] = "2026-03-15"
                hidden["wage_period"] = "2026年3月"
                hidden["wage_owed"] = 5000
            ref_specs = [s for c in claims for s in specs_for(c, hidden)]
            case = {"id": f"B{index * 3 + variant + 1:02d}", "split": "dev" if variant == 0 else "test",
                    "primary_claim": claim, "claims_gold": claims, "opening": text,
                    "opening_variants": [text, "麻烦帮我看看：" + text, "我有点着急，" + text],
                    "opening_facts": opening_facts, "hidden": hidden,
                    "critical": critical_keys(claims, hidden, schema),
                    "answers": {k: answer_text(k, v, schema["facts"]) for k, v in hidden.items()},
                    "tags": ["ordinary" if variant < 2 else "challenge"] + (["multi_claim"] if len(claims) > 1 else []),
                    "reference_specs": ref_specs, "sources": list(SOURCES.values()),
                    "assumptions": ["合成咨询，不对应真实裁判；金标准仅在列明假设下有效。",
                                    "日期为公历精确日期；未建模时效中止、中断和地区口径。",
                                    "工资基数视为已经核实且不触发地方封顶；不验证地方最低工资。",
                                    "年假为完整年度、无不享受情形、正常工资已付；工伤仅算七至十级一次性伤残补助金。",
                                    "竞业补偿按明确约定且已履行期间计算；未作裁判结果预测。"],
                    "review": {"human_status": "pending", "model_status": "not_run", "gold_status": "provisional"}}
            case["gold_before"] = reference_gold(case, hidden, "2026-11-27")
            if variant == 1:
                key, new = correction
                old = hidden[key]
                after = {**hidden, key: new}
                case["correction"] = {"after": "first_memo", "key": key, "old": old, "new": new,
                                      "text": "更正一下，我之前说错了。" + answer_text(key, new, schema["facts"])}
                case["gold_after"] = reference_gold(case, after, "2026-11-27")
                case["critical_after"] = critical_keys(claims, after, schema)
                case["tags"].append("correction")
            else:
                case["gold_after"] = case["gold_before"]
            if any(v is None for v in hidden.values()):
                case["tags"].append("unavailable_fact")
            cases.append(case)
    # Cover three missing conditional-field sides without changing the original 36 cases.
    for cid, who, reason, pay, opening in [
        ("B37", "劳动者辞职", "其他或说不清", "0", "我自己辞职，想问解除劳动合同后还有经济补偿吗？"),
        ("B38", "单位单方解除", "合同期满不续签", "N", "劳动合同到期，公司不续签，经济补偿应该怎么算？"),
    ]:
        case = copy.deepcopy(cases[0])
        case.update(id=cid, split="test", opening=opening,
                    opening_variants=[opening, "麻烦帮我看看：" + opening, "我有点着急，" + opening],
                    opening_facts={"who_initiated": who} if cid == "B37" else
                    {"stated_reason": reason, "contract_expired": "合同到期不续签"},
                    tags=["challenge", "branch_boundary"])
        case["hidden"].update(who_initiated=who, stated_reason=reason, forced_resignation_reason="不适用",
                              pregnancy_status="不是")
        if cid == "B38":
            case["hidden"]["contract_expired"] = "合同到期不续签"
        case["critical"] = critical_keys(case["claims_gold"], case["hidden"], schema)
        case["answers"] = {k: answer_text(k, v, schema["facts"]) for k, v in case["hidden"].items()}
        case["reference_specs"] = specs_for("labor_dismissal", case["hidden"])
        case["reference_specs"][0]["value"] = False
        case["reference_specs"][0]["depends"] = ["who_initiated", "stated_reason"]
        case["reference_specs"][1]["pay_type"] = pay
        case["gold_before"] = reference_gold(case, case["hidden"], "2026-11-27")
        case["gold_after"] = case["gold_before"]
        cases.append(case)
    return {"version": "2.0.1", "today": "2026-11-27", "generation_mode": "curated_template",
            "revision_note": "B36开场补明劳动领域，避免把其他领域仲裁也合理需要的分诊澄清误算作错误；未改变隐藏事实和断言值。",
            "gold_notice": "独立公式+作者指定行为标签；未经律师/人工审定，不称法律能力基准。",
            "cases": cases}


def build_router():
    rows = [
        ("公司拖欠工资，我该怎么办？", "proceed", ["labor_wage"]),
        ("公司欠薪还让我天天加班。", "proceed", ["labor_wage", "labor_overtime"]),
        ("我想问未休年假工资。", "proceed", ["labor_annual_leave"]),
        ("车祸之后保险公司不赔，交通事故怎么处理？", "proceed", ["tort_injury"]),
        ("我要离婚，孩子抚养权归谁？", "out_of_scope", []),
        ("朋友借钱不还，借贷欠条怎么起诉？", "out_of_scope", []),
        ("房东不退租房押金，租赁纠纷怎么办？", "out_of_scope", []),
        ("涉嫌诈骗被刑事拘留了，怎么办？", "out_of_scope", []),
        ("我遇到了麻烦，想咨询一下。", "clarify", []),
        ("对方这么做合理吗？", "clarify", []),
        ("我应该准备什么材料？", "clarify", []),
        ("我现在很着急，不知道下一步怎么办。", "clarify", []),
    ]
    return {"version": "2.0.0", "cases": [{"id": f"R{i+1:02d}", "opening": t,
              "action_gold": a, "claims_gold": c, "human_status": "pending"}
             for i, (t, a, c) in enumerate(rows)]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data/eval")
    ap.add_argument("--rewrite-api", action="store_true", help="optional model surface rewrites; facts and gold stay fixed")
    ap.add_argument("--model", help="surface generator model; uses LLM_MODEL if omitted")
    args = ap.parse_args()
    if args.rewrite_api and args.out_dir.resolve() == (ROOT / "data/eval").resolve():
        ap.error("API rewrites must use a new --out-dir; do not overwrite the frozen corpus")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    data = build_cases()
    if args.rewrite_api:
        from lexflow.config import LLMConfig
        from lexflow.llm import build_llm, extract_json
        from api_audit import AuditedLLM
        cfg = LLMConfig(mode="api")
        if args.model:
            cfg.model = args.model
        try:
            model = AuditedLLM(build_llm(cfg, strict=True))
        except ValueError as exc:
            ap.error(str(exc))
        for c in data["cases"]:
            result = model.complete([
                {"role": "system", "content": "把咨询开场改写为自然口语。保持原文事实和疑问不变，不新增日期、金额、法律结论或其他事实。只输出JSON：{\"opening\":\"...\"}。"},
                {"role": "user", "content": c["opening"]},
            ], temperature=0.3, max_tokens=400)
            parsed = extract_json(result.text) if result.ok else None
            if not isinstance(parsed, dict) or not isinstance(parsed.get("opening"), str) or not parsed["opening"].strip():
                raise SystemExit(f"surface generation failed for {c['id']}; no corpus was approved or saved")
            c["opening_variants"][2] = parsed["opening"].strip()
            c["review"]["surface_status"] = "model_rewrite_unreviewed"
        data["version"] = "2.1.0-unreviewed-surfaces"
        data["generation_mode"] = "curated_facts_with_api_surface_rewrite"
        data["generator_model"] = cfg.model
        data["generation_usage"] = model.summary()
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    target = args.out_dir / "labor_cases_v2.json"
    target.write_text(payload, encoding="utf-8")
    (args.out_dir / "router_cases_v2.json").write_text(json.dumps(build_router(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.out_dir / "coverage_plan.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "split", "primary_claim", "all_claims", "challenge_tags", "correction_field", "source"])
        writer.writeheader()
        for c in data["cases"]:
            writer.writerow({"case_id": c["id"], "split": c["split"], "primary_claim": c["primary_claim"],
                             "all_claims": ";".join(c["claims_gold"]), "challenge_tags": ";".join(c["tags"]),
                             "correction_field": c.get("correction", {}).get("key", ""), "source": "curated_synthetic"})
    (args.out_dir / "labor_cases_v2.sha256").write_text(hashlib.sha256(payload.encode()).hexdigest() + "  labor_cases_v2.json\n")
    print(json.dumps({"cases": len(data["cases"]), "dev": sum(c['split'] == 'dev' for c in data['cases']),
                      "test": sum(c['split'] == 'test' for c in data['cases']), "router": 12,
                      "generation_mode": data["generation_mode"], "human_review": "pending"}))


if __name__ == "__main__":
    main()

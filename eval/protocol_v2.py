"""End-to-end, bounded, observable consultation protocol with annotated disclosure."""
from __future__ import annotations

import copy
import time
from dataclasses import asdict

from lexflow.agent import ConsultationAgent
from lexflow.config import Budget
from lexflow.memory import MemoryStore
from lexflow.verify import Verifier
from api_audit import AuditedLLM
from metrics_v2 import (UNKNOWN, active_facts, claim_scores, fact_scores, question_scores,
                        ratio, revision_score, score_assertions)
from protocol import CONDITIONS


class ScriptedClientV2:
    """Question keys address the sheet; this does NOT assess question wording."""
    def __init__(self, case, variant=0):
        self.case = case
        self.hidden = dict(case["hidden"])
        self.disclosed = dict(case["opening_facts"])
        self.variant = variant

    def answer(self, questions):
        parts = []
        for q in questions:
            key = q["key"]
            if key in self.hidden:
                self.disclosed[key] = self.hidden[key]
                text = self.case["answers"][key]
                # After correction, only the corrected value changes; the prewritten answer is obsolete.
                correction = self.case.get("correction", {})
                if key == correction.get("key") and self.hidden[key] == correction.get("new"):
                    text = correction["text"]
                parts.append(text)
            else:
                parts.append("这个我确实不清楚。")
        prefix = ("", "我能确认的是：", "我再说明一下：")[self.variant % 3]
        return prefix + "".join(parts)

    def correct(self):
        c = self.case["correction"]
        self.hidden[c["key"]] = c["new"]
        self.disclosed[c["key"]] = c["new"]
        return c["text"]


def run_case(case, condition, corpus, schema, llm, today, *, variant=0, max_turns=12, max_questions=14):
    store = MemoryStore(":memory:")
    audit = AuditedLLM(llm)
    agent = ConsultationAgent(corpus, schema, store, llm=audit, today=today,
                              budget=Budget(max_questions=max_questions), **CONDITIONS[condition])
    session = f"v2-{case['id']}-{condition}-{variant}"
    client = ScriptedClientV2(case, variant)
    records, question_keys = [], []
    extraction_sources = []
    started = time.perf_counter()

    def handle(text, phase):
        # Only conversational text enters the system. No claims_gold / case_type / hidden / gold.
        result = agent.handle(session, text)
        records.append({"phase": phase, "user_text": text, "result": copy.deepcopy(result.to_dict())})
        extraction_sources.extend(t["source"] for t in result.trace if t.get("node") == "fact_extraction")
        return result

    def follow(result, phase):
        exchanges = 0
        while result.status == "asked" and exchanges < max_turns:
            remaining = max_questions - len(question_keys)
            # The production budget should enforce this; preserve violations as evidence.
            if remaining < len(result.questions):
                break
            question_keys.extend(q["key"] for q in result.questions)
            text = client.answer(result.questions)
            result = handle(text, phase)
            exchanges += 1
        return result

    try:
        first = handle(case["opening_variants"][variant % len(case["opening_variants"])], "initial")
        initial_route = copy.deepcopy(first.route)
        first = follow(first, "initial")
        first_snapshot = copy.deepcopy(first.to_dict())
        first_facts = active_facts(first.facts)
        first_scores = fact_scores(first_facts, client.disclosed, client.hidden, case["critical"])
        first_disclosed = dict(client.disclosed)
        first_question_keys = list(question_keys)
        correction_applied = bool(case.get("correction") and first.status == "answered")
        final = first
        if correction_applied:
            final = follow(handle(client.correct(), "correction"), "correction")
        elapsed_ms = (time.perf_counter() - started) * 1000
        final_facts = active_facts(final.facts)
        final_critical = case.get("critical_after", case["critical"]) if correction_applied else case["critical"]
        scores = fact_scores(final_facts, client.disclosed, client.hidden, final_critical)
        scores.update(question_scores(question_keys, case["critical"], case["opening_facts"]))
        scores.update(claim_scores(initial_route.get("claims", []), case["claims_gold"]))
        gold = case["gold_after"] if correction_applied else case["gold_before"]
        assertions = score_assertions(final.analysis, gold)
        applicable = [r for r in assertions if r["applicable"]]
        formula = [r for r in applicable if r["reference_kind"] == "independent_formula"]
        behaviors = [r for r in applicable if r["reference_kind"] == "author_specified_behavior"]
        scores["outcome_agreement"] = ratio(sum(bool(r["ok"]) for r in applicable), len(applicable))
        scores["formula_agreement"] = ratio(sum(bool(r["ok"]) for r in formula), len(formula))
        scores["behavior_agreement"] = ratio(sum(bool(r["ok"]) for r in behaviors), len(behaviors))
        scores["outcome_all_correct"] = all(r["ok"] for r in applicable) if applicable else None
        scores["completed"] = final.status == "answered"
        scores["first_correct_coverage"] = first_scores["correct_coverage"]
        # Explicitly a structural proxy, not a semantic legal-advice judgment.
        scores["premature_unqualified_memo_proxy"] = bool(first.status == "answered" and
            first_scores["missing_or_wrong_critical"] and not first.analysis.get("gaps"))
        unavailable = [k for k in final_critical if client.hidden.get(k) is None]
        scores["unknown_handling_proxy"] = (all(k not in final_facts for k in unavailable) and
            (final.status == "asked" or bool(final.analysis.get("gaps")))) if unavailable else None
        verification = {"checked": 0, "support_rate": None, "defects": []}
        if final.analysis:
            verification = Verifier(corpus).verify(agent._analysis_from_dict(final.analysis), store.load(session))
        scores["citation_mechanical_support"] = verification["support_rate"] if verification["checked"] else None
        revision = None
        if correction_applied:
            revision = revision_score(first_snapshot["analysis"], final.analysis, case["gold_after"],
                                      {case["correction"]["key"]: case["correction"]["new"]}, final_facts, client.disclosed)
        scores["correction_protocol_complete"] = correction_applied if case.get("correction") else None
        scores["revision_success"] = (revision["corrected_facts_ok"] and
            revision["affected_outcomes_ok"] is not False and final.status == "answered") if revision else None
        scores["unaffected_preserved"] = revision["unaffected_preserved"] if revision else None
        usage = audit.summary()
        scores["fallback_extractions"] = sum(source != "llm" for source in extraction_sources) if audit.enabled else 0
        scores["fallback_extraction_rate"] = ratio(scores["fallback_extractions"], len(extraction_sources)) if audit.enabled else None
        failures = []
        if final.status != "answered":
            failures.append("budget_exhausted" if final.status == "asked" else f"route_{final.status}")
        if not scores["claim_exact"]:
            failures.append("initial_claim_mismatch")
        if scores["missing_or_wrong_critical"]:
            failures.append("missing_or_wrong_critical_facts")
        if any(r["ok"] is False for r in assertions):
            failures.append("reference_disagreement")
        if usage["failed_calls"] or scores["fallback_extractions"]:
            failures.append("api_failure_or_extraction_fallback")
        return {"case_id": case["id"], "split": case["split"], "primary_claim": case["primary_claim"],
                "condition": condition, "variant": variant, "status": final.status,
                "scores": scores, "assertions": assertions, "revision": revision,
                "elapsed_ms": round(elapsed_ms, 2), "turns": len(records), "usage": usage,
                "initial_route": initial_route, "first_scores": first_scores,
                "first_disclosed_facts": first_disclosed, "first_question_keys": first_question_keys,
                "disclosed_facts": client.disclosed, "active_facts": final_facts,
                "offline_verification": verification, "failures": failures,
                "model_calls": audit.events, "trajectory": records}
    finally:
        store.close()

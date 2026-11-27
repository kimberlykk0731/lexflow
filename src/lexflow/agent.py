"""The consultation agent: route → intake → element gate → research → memo → verify.

Control flow is deterministic so ablations isolate one mechanism at a time.
The model is used for fact extraction, optional routing disambiguation, and a
short plain-language explanation.  Conclusions, citations and arithmetic come
from the rule layer.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date

from .config import Budget, LLMConfig
from .corpus import StatuteCorpus
from .elements import ElementSchema, Field
from .extract import Extractor
from .issues import IssueTree, Question
from .knowledge import KnowledgeBase
from .llm import BaseLLM, build_llm
from .memory import CaseState, MemoryStore
from .memo import MemoBuilder
from .questions import QuestionComposer
from .router import MatterRouter
from .rules import Analysis, _cite_short
from .tools import BudgetExceeded, ToolBox
from .verify import Verifier
from .voi import ScenarioVOI


@dataclass
class TurnResult:
    session: str
    turn: int
    status: str
    reply: str
    questions: list[dict] = field(default_factory=list)
    memo: str = ""
    analysis: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    facts: list[dict] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    invalidated_cache: int = 0
    revision: int = 0
    tools: dict = field(default_factory=dict)
    conflicts: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    claims: list[str] = field(default_factory=list)
    route: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    chain: list[dict] = field(default_factory=list)
    voi: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ConsultationAgent:
    """A rule-controlled, LLM-assisted legal consultation agent."""

    def __init__(self, corpus: StatuteCorpus, schema: ElementSchema,
                 store: MemoryStore, llm: BaseLLM | None = None,
                 budget: Budget | None = None,
                 use_gate: bool = True, use_verify: bool = True,
                 use_repair: bool = True, use_memory: bool = True,
                 use_cache: bool = True, use_revision: bool = True,
                 use_voi: bool = True, today: str | None = None,
                 knowledge: KnowledgeBase | None = None):
        self.corpus = corpus
        self.schema = schema
        self.store = store
        self.llm = llm or build_llm(LLMConfig())
        self.budget = budget or Budget()
        self.today = today or date.today().isoformat()
        self.extractor = Extractor(schema, self.llm, today=date.fromisoformat(self.today))
        self.memo_builder = MemoBuilder(corpus, schema)
        self.verifier = Verifier(corpus)
        self.router = MatterRouter(schema, self.llm)
        self.issues = IssueTree(schema)
        self.composer = QuestionComposer(self.llm)
        self.knowledge = knowledge or KnowledgeBase()
        self.voi = ScenarioVOI(self.today)
        self.use_gate = use_gate
        self.use_verify = use_verify
        self.use_repair = use_repair
        self.use_memory = use_memory
        self.use_cache = use_cache
        self.use_revision = use_revision
        self.use_voi = use_voi
        self.turn_no = 0
        self.note_usage = {"prompt": 0, "completion": 0, "calls": 0}
        self._turn_usage_start = {"prompt": 0, "completion": 0, "calls": 0}

    # ------------------------------------------------------------- public
    def handle(self, session: str, text: str, document: str | None = None,
               force_memo: bool = False, case_type: str | None = None) -> TurnResult:
        started = time.perf_counter()
        self._turn_usage_start = self._usage_now()
        state = self.store.load(session) if self.use_memory else CaseState(session)
        self.turn_no += 1
        turn = self.turn_no
        trace: list[dict] = [{"node": "input", "text": text},
                             {"node": "session_load", "revision": state.revision,
                              "facts": len(state.facts)}]

        # 0) route + optional switch --------------------------------------
        if case_type:
            route = self._forced_route(case_type)
        else:
            route = self.router.route(text, state)
        trace.append({"node": "route", **route.to_dict()})

        if route.action in ("clarify", "out_of_scope") and not (force_memo and state.claims):
            status = "clarify" if route.action == "clarify" else "out_of_scope"
            self.store.log_turn(session, turn, "user", text,
                                {"case_type": state.case_type, "route": route.to_dict()})
            return self._finish(state, turn, status, route.reply, trace, started,
                                claims=state.claims, route=route.to_dict(),
                                coverage=self.issues.coverage(state.claims, state.values())
                                if state.claims else {})

        if route.action == "switch" and state.claims:
            state.asked = []
            state.ask_counts = {}
            state.last_analysis = None
            state.claims = []
        if route.claims:
            if state.matter == route.matter and route.action != "switch":
                state.claims = list(dict.fromkeys(state.claims + route.claims))
            else:
                state.claims = list(route.claims)
        if route.matter:
            state.matter = route.matter
        if not state.claims:
            self.store.log_turn(session, turn, "user", text, {"case_type": ""})
            return self._finish(state, turn, "clarify", self.router._clarify_reply(),
                                trace, started, route=route.to_dict())
        state.case_type = state.claims[0]
        state.route = route.to_dict()
        self.store.log_turn(session, turn, "user", text,
                            {"case_type": state.case_type, "claims": state.claims})

        # 1) intake -------------------------------------------------------
        extracted = self.extractor.extract(text, state.values(), state.claims)
        trace.append({"node": "fact_extraction", "source": self.extractor.last_source})
        changed: list[str] = []
        conflicts: list[dict] = []
        for key, value in extracted["facts"].items():
            is_correction = (key in extracted["corrections"]) or extracted.get("correction_hint")
            old = state.facts.get(key)
            if (old is not None and old.status == "documentary"
                    and str(old.value) != str(value)):
                conflicts.append({"key": key, "documented": old.value, "user_said": value})
                trace.append({"node": "fact_conflict", "key": key,
                              "documented": old.value, "user_said": value})
                continue
            field = self.schema.field_any(key)
            refine = bool(field and field.type == "date" and old is not None
                          and str(old.value).endswith("-01")
                          and str(value)[:7] == str(old.value)[:7])
            may_update = (old is None or is_correction or key in state.asked
                          or (old is not None and old.status == "unknown") or refine)
            if old is not None and str(old.value) != str(value) and not may_update:
                trace.append({"node": "fact_kept", "key": key,
                              "kept": old.value, "ignored": value,
                              "reason": "no explicit correction"})
                continue
            ok, changed_keys = state.set_fact(
                key, value, status="user_stated", source="user", turn=turn,
                overwrite=True, precision=extracted.get("precision", {}).get(key, "day"))
            if ok:
                changed.extend(changed_keys)
                self.store.log_fact(state, state.facts[key])
                trace.append({"node": "fact_set", "key": key, "value": value,
                              "correction": bool(is_correction)})
        for key in extracted.get("unknown", []):
            if state.mark_unknown(key, turn):
                changed.append(key)
                trace.append({"node": "fact_unknown", "key": key})

        invalidated = self.store.invalidate(changed, state) if changed else 0
        if changed:
            trace.append({"node": "cache_invalidate", "keys": changed,
                          "entries": invalidated, "revision": state.revision})

        if document:
            doc = self._read_document(state, state.claims, document, turn)
            changed.extend(doc)
            trace.append({"node": "document_intake", "facts": doc})

        # 2) element gate -------------------------------------------------
        facts = self._facts(state)
        coverage = self.issues.coverage(state.claims, facts)
        precisions = {k: f.precision for k, f in state.facts.items()}
        frontier = self.issues.frontier(state.claims, facts, precisions=precisions)
        asked_now: list[Question] = []
        voi_scores: dict = {}
        skipped_by_voi: list[str] = []
        if self.use_gate and frontier and not force_memo:
            if len(state.asked) < self.budget.max_questions:
                voi_scores = {}
                if self.use_voi:
                    voi_scores = self.voi.score(frontier, state.claims, facts)
                    trace.append({"node": "voi", "scores": {
                        k: v.to_dict() for k, v in voi_scores.items()}})
                asked_now = self.issues.next_questions(
                    state.claims, facts, n=min(2, self.budget.max_questions - len(state.asked)), ask_counts=state.ask_counts,
                    precisions=precisions, voi=voi_scores)
                # If every remaining critical question is outcome-neutral and
                # no "must ask" fact is left, stop and answer with gaps.
                must_ask = {"claim_type", "start_date", "monthly_wage",
                            "dismiss_date", "injury_date", "wage_owed",
                            "wage_period", "no_contract_months", "overtime_exists",
                            # Procedural facts change available steps and deadlines,
                            # even when the monetary scenario signature is unchanged.
                            "arbitration_date", "arbitration_result", "court_filed",
                            "deadline_aware"}
                remaining_keys = {q.key for q in frontier}
                if (self.use_voi and voi_scores
                        and len(voi_scores) >= len(frontier)
                        and not (remaining_keys & must_ask)
                        and all(v.gain <= 0 for v in voi_scores.values())):
                    skipped_by_voi = [q.key for q in frontier]
                    asked_now = []
            if asked_now:
                for q in asked_now:
                    state.asked.append(q.key)
                    state.ask_counts[q.key] = state.ask_counts.get(q.key, 0) + 1
                reply = self._ask_reply(asked_now, state, changed, conflicts,
                                        voi_scores)
                trace.append({"node": "gate", "decision": "ask",
                              "missing": [q.key for q in frontier],
                              "asked": [q.key for q in asked_now],
                              "coverage": coverage})
                return self._finish(
                    state, turn, "asked", reply, trace, started,
                    questions=[self._q(q) for q in asked_now], changed=changed,
                    invalidated=invalidated, conflicts=conflicts, claims=state.claims,
                    route=route.to_dict(), coverage=coverage,
                    chain=self.issues.chain(state.claims, facts),
                    voi={k: v.to_dict() for k, v in voi_scores.items()})
            trace.append({"node": "gate", "decision": "answer_with_gaps",
                          "missing": [q.key for q in frontier],
                          "skipped_by_voi": skipped_by_voi,
                          "reason": ("remaining questions do not change the outcome"
                                     if skipped_by_voi else
                                     "question budget exhausted or forced")})
        elif frontier:
            trace.append({"node": "gate", "decision": "skip_gate",
                          "missing": [q.key for q in frontier]})
        else:
            trace.append({"node": "gate", "decision": "ready", "missing": []})

        # 3) research -----------------------------------------------------
        toolbox = ToolBox(self.corpus, self.store, state, self.budget)
        critical_keys = [f.key for f in self.schema.fields(state.claims)
                         if self.schema.is_critical(f, facts, f.claim)]
        research: dict = {}
        try:
            if not self.use_revision and state.last_analysis:
                analysis = self._analysis_from_dict(state.last_analysis)
                trace.append({"node": "analysis_reused",
                              "from_revision": state.revision - 1})
                res = {"evidence_ids": [], "cached": True}
            else:
                res = toolbox.call("analyse_many",
                                   {"claims": state.claims, "facts": facts,
                                    "today": self.today, "revision": state.revision},
                                   deps=critical_keys)
                if not res.get("ok"):
                    raise RuntimeError(res.get("error", "analysis failed"))
                analysis = self._analysis_from_dict(res["analysis"])
                state.last_analysis = analysis.to_dict()
            research["analysis_evidence"] = res.get("evidence_ids", [])
            research["analysis_cached"] = res.get("cached", False)
            trace.append({"node": "tool:analyse_many",
                          "cached": res.get("cached", False),
                          "findings": len(analysis.findings)})

            # attach the element chain + coverage + practice notes
            analysis.metadata["chain"] = self.issues.chain(state.claims, facts)
            analysis.metadata["coverage"] = coverage
            analysis.metadata["proof_checklist"] = self.issues.proof_checklist(
                state.claims, facts)
            analysis.metadata["claims"] = state.claims
            rag_query = " ".join(self.schema.label(c) for c in state.claims)
            rag_query += " " + " ".join(
                f.issue + " " + f.conclusion[:40] for f in analysis.findings[:4])
            notes = self.knowledge.retrieve(rag_query, state.claims, k=4)
            if notes:
                analysis.metadata["practice_notes"] = notes
                analysis.metadata["rag_query"] = rag_query
                trace.append({"node": "rag", "query": rag_query,
                              "hits": [{"id": n.get("id"), "score": n.get("score")}
                                       for n in notes]})

            # residual value of information: what would still be worth asking
            residual = self.issues.frontier(state.claims, facts)
            if residual and self.use_voi:
                analysis.metadata["voi"] = {
                    k: v.to_dict() for k, v in
                    self.voi.score(residual, state.claims, facts).items()}
            else:
                analysis.metadata["voi"] = {}

            # Retrieval check: would the cited articles be retrieved for the
            # issues the analysis raises?  Diagnostic, not correctness.
            retrieval_hits = 0
            law_hints = self.schema.law_hints(state.claims)
            for finding in analysis.findings:
                query = finding.issue + " " + finding.conclusion[:40]
                r = toolbox.call("search_statute",
                                 {"query": query, "as_of": analysis.as_of or None,
                                  "law_hints": law_hints, "k": 5}, deps=[])
                ids = [h["id"] for h in r.get("results", [])]
                hit = any(c in ids for c in finding.cites)
                retrieval_hits += 1 if hit else 0
                research.setdefault("retrieval", []).append(
                    {"finding": finding.id, "top": ids[:3], "cited": finding.cites,
                     "hit": hit})
            research["retrieval_support"] = (
                round(retrieval_hits / len(analysis.findings), 4)
                if analysis.findings else 0.0)

            for aid in dict.fromkeys(c for f in analysis.findings for c in f.cites):
                toolbox.call("get_article", {"article_id": aid}, deps=[])
        except BudgetExceeded as exc:
            trace.append({"node": "budget", "error": str(exc)})
            analysis = Analysis(case_type=state.claims[0], as_of="",
                                headline="工具预算已用完，无法完成检索。", findings=[],
                                gaps=[str(exc)], assumptions=[])
        except Exception as exc:  # keep the consultation alive
            trace.append({"node": "error", "error": f"{type(exc).__name__}: {exc}"})
            analysis = Analysis(case_type=state.claims[0], as_of="",
                                headline="分析阶段出错。", findings=[],
                                gaps=[f"{type(exc).__name__}: {exc}"], assumptions=[])

        still_missing = self.schema.missing(state.claims, facts)
        if skipped_by_voi:
            still_missing = [f for f in still_missing if f.key not in skipped_by_voi]
        if still_missing:
            analysis.gaps.insert(0, "以下关键事实尚未取得，结论只能在有限范围内成立："
                                + "、".join(f.label for f in still_missing))
        if skipped_by_voi:
            analysis.gaps.insert(0, "以下事实未采集，因为它们不改变当前结论："
                                + "、".join(self.schema.field_any(k).label
                                           if self.schema.field_any(k) else k
                                           for k in skipped_by_voi))
        month_dates = [f.label for f in self.schema.fields(state.claims)
                       if f.type == "date" and state.facts.get(f.key)
                       and state.facts[f.key].precision == "month"]
        if month_dates:
            analysis.gaps.insert(1, "以下日期只精确到月（" + "、".join(month_dates)
                                + "），可能影响时效与年限计算。")

        # 4) verify + bounded repair -------------------------------------
        verification = (self.verifier.verify(analysis, state) if self.use_verify else
                        {"checked": 0, "supported": 0, "support_rate": 0.0,
                         "defects": [], "skipped": True})
        if self.use_verify and verification["defects"] and self.use_repair:
            repaired = self._repair(analysis, verification, state)
            if repaired:
                verification = self.verifier.verify(analysis, state)
                trace.append({"node": "repair", "applied": repaired,
                              "defects_left": len(verification["defects"])})
        trace.append({"node": "verify", "support_rate": verification["support_rate"],
                      "defects": verification["defects"],
                      "skipped": not self.use_verify})

        # 5) memo ---------------------------------------------------------
        llm_note = self._llm_note(analysis) if self.llm.enabled else None
        memo = self.memo_builder.render(analysis, state, verification, llm_note)
        reply = self._answer_reply(analysis, state, verification, changed)
        trace.append({"node": "memo", "chars": len(memo)})

        if conflicts:
            analysis.gaps.append("事实冲突：" + "；".join(
                f"{c['key']} 的材料记载为 {c['documented']}，您说的是 {c['user_said']}"
                for c in conflicts) + "。请核对原件后确认。")
        return self._finish(
            state, turn, "answered", reply, trace, started,
            memo=memo, analysis=analysis.to_dict(), verification=verification,
            changed=changed, invalidated=invalidated, conflicts=conflicts,
            tools=toolbox.summary(), claims=state.claims, route=route.to_dict(),
            coverage=coverage, chain=analysis.metadata.get("chain", []),
            voi=analysis.metadata.get("voi", {}) or
                {k: v.to_dict() for k, v in (voi_scores or {}).items()},
            metrics={"retrieval_support": research.get("retrieval_support", 0.0),
                     "cached_tools": toolbox.n_cached,
                     "executed_tools": toolbox.n_executed,
                     "coverage_rate": coverage.get("rate", 0.0)})

    # ------------------------------------------------------------- helpers
    def _facts(self, state: CaseState) -> dict:
        return {k: v for k, v in state.values().items()
                if v not in ("不清楚", "记不清", "说不清")}

    def _forced_route(self, case_type: str):
        from .router import Route
        matter = self.schema.claims.get(case_type, {}).get("matter", "labor")
        return Route(matter=matter, claims=[case_type], confidence=1.0,
                     action="proceed", source="forced")

    def _read_document(self, state: CaseState, claims: list[str], text: str,
                       turn: int) -> list[str]:
        changed: list[str] = []
        extracted = self.extractor.extract(text, state.values(), claims)
        for key, value in extracted["facts"].items():
            ok, keys = state.set_fact(key, value, status="documentary",
                                      source="document", turn=turn,
                                      precision=extracted.get("precision", {}).get(key, "day"))
            if ok:
                changed.extend(keys)
                self.store.log_fact(state, state.facts[key])
        return changed

    # ------------------------------------------------------------- replies
    def _q(self, q: Question) -> dict:
        return {"key": q.key, "label": q.field.label, "question": q.field.question,
                "why": q.field.why, "element": q.element_label, "claim": q.claim}

    def _ask_reply(self, asked: list[Question], state: CaseState,
                   changed: list[str] | None = None,
                   conflicts: list[dict] | None = None,
                   voi: dict | None = None) -> str:
        facts = self._facts(state)
        labels = {c: self.schema.label(c) for c in state.claims}
        lines = []
        ack = self._ack(state, changed or [])
        if ack:
            lines += [ack, ""]
        if conflicts:
            parts = []
            for c in conflicts:
                f = self.schema.field_any(c["key"])
                parts.append(f"{f.label if f else c['key']} 的材料记载为 "
                             f"{c['documented']}，您说的是 {c['user_said']}")
            lines += ["⚠️ " + "；".join(parts) + "。我先保留材料记载，请核对原件后再确认。", ""]
        lines += [self.composer.intro(state.claims, labels, facts), ""]
        texts = self.composer.compose_many(asked, facts, labels)
        for i, (q, text) in enumerate(zip(asked, texts), 1):
            lines.append(f"{i}. {text}")
            if q.field.why:
                lines.append(f"   （为什么问：{q.field.why}）")
            if voi and q.key in voi and voi[q.key].gain > 0:
                lines.append(f"   （信息价值：{voi[q.key].reason}）")
        remaining = len(self.issues.frontier(
            state.claims, facts,
            precisions={k: f.precision for k, f in state.facts.items()}))
        if remaining > 0:
            lines.append("")
            lines.append(f"另外还有 {remaining} 项信息待补充，可以稍后再说。")
        lines.append("")
        lines.append("您可以直接用大白话回答，不用管法律术语。")
        return "\n".join(lines)

    def _ack(self, state: CaseState, changed: list[str]) -> str:
        parts = []
        for key in dict.fromkeys(changed):
            f = self.schema.field_any(key)
            if not f or key not in state.facts:
                continue
            value = state.facts[key].value
            if isinstance(value, float):
                value = f"{value:,.0f}"
            parts.append(f"{f.label}＝{value}")
        return ("已记录：" + "；".join(parts) + "。") if parts else ""

    def _answer_reply(self, analysis: Analysis, state: CaseState, verification: dict,
                      changed: list[str] | None = None) -> str:
        lines = []
        ack = self._ack(state, changed or [])
        if ack:
            lines += [ack, ""]
        labels = "、".join(self.schema.label(c) for c in state.claims)
        lines += [f"根据目前记录的事实（{labels}），初步判断如下：", "", analysis.headline]
        high = [f for f in analysis.findings if f.risk == "高"]
        if high:
            lines += ["", "**风险提示**：" + "；".join(f.issue for f in high[:3])]
        if analysis.gaps:
            lines += ["", "**尚不能确定**："]
            lines += [f"- {g}" for g in analysis.gaps[:6]]
        if verification.get("defects"):
            lines += ["", f"（自动核验发现 {len(verification['defects'])} 处需要人工复核的地方，"
                          "见备忘录。）"]
        lines += ["", "完整的备忘录（要件链、事实状态、争点依据、证据清单）已生成。"]
        lines += ["您还可以让我出：法律意见书、劳动仲裁申请书、证据清单、"
                  "被迫解除通知书，或做「仲裁 vs 诉讼」对比。"]
        return "\n".join(lines)

    def _usage_now(self) -> dict:
        ext = self.extractor.usage
        note = self.note_usage
        return {"prompt": ext["prompt"] + note["prompt"],
                "completion": ext["completion"] + note["completion"],
                "calls": ext["calls"] + note["calls"]}

    def _llm_note(self, analysis: Analysis) -> str | None:
        payload = {
            "headline": analysis.headline,
            "findings": [{"issue": f.issue, "conclusion": f.conclusion, "risk": f.risk}
                         for f in analysis.findings[:6]],
        }
        res = self.llm.complete([
            {"role": "system", "content": (
                "你是法律咨询助理。用当事人能听懂的话，把下面的结论解释成 2-3 句话。"
                "不得新增事实、金额、日期或法条，不得改变风险判断，只做解释。")},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ], temperature=0.2, max_tokens=300)
        if res.ok:
            self.note_usage["prompt"] += res.prompt_tokens
            self.note_usage["completion"] += res.completion_tokens
            self.note_usage["calls"] += 1
        return res.text.strip() if res.ok and res.text.strip() else None

    # ------------------------------------------------------------- repair
    def _repair(self, analysis: Analysis, verification: dict, state: CaseState) -> list[str]:
        applied: list[str] = []
        by_id = {f.id: f for f in analysis.findings}
        for defect in verification["defects"]:
            finding = by_id.get(defect["claim_id"])
            if not finding:
                continue
            if defect["code"] == "VERSION_NOT_IN_FORCE":
                new_cites = []
                for cid in finding.cites:
                    art = self.corpus.get(cid)
                    valid = self.corpus.find(art.law_id, art.article_no, analysis.as_of) if art else None
                    new_cites.append(valid.id if valid else cid)
                if new_cites != finding.cites:
                    finding.cites = new_cites
                    applied.append(f"replaced-version:{finding.id}")
            elif defect["code"] == "QUOTE_MISMATCH":
                finding.quote = ""
                applied.append(f"dropped-quote:{finding.id}")
            elif defect["code"] == "UNKNOWN_SOURCE":
                finding.cites = [c for c in finding.cites if self.corpus.get(c)]
                applied.append(f"dropped-unknown-source:{finding.id}")
        return applied

    # ------------------------------------------------------------- helpers
    def _analysis_from_dict(self, d: dict) -> Analysis:
        from .rules import Finding
        findings = [Finding(**f) for f in d["findings"]]
        return Analysis(case_type=d["case_type"], as_of=d["as_of"],
                        headline=d["headline"], findings=findings,
                        gaps=d.get("gaps", []), assumptions=d.get("assumptions", []),
                        metadata=d.get("metadata", {}))

    def _usage_delta(self) -> dict:
        now = self._usage_now()
        start = self._turn_usage_start
        return {"prompt_tokens": now["prompt"] - start["prompt"],
                "completion_tokens": now["completion"] - start["completion"],
                "llm_calls": now["calls"] - start["calls"]}

    def _finish(self, state: CaseState, turn: int, status: str, reply: str,
                trace: list[dict], started: float, **kwargs) -> TurnResult:
        self.store.save(state)
        self.store.log_turn(state.session, turn, "assistant", reply,
                            {"status": status})
        result = TurnResult(
            session=state.session, turn=turn, status=status, reply=reply,
            facts=state.fact_table(), revision=state.revision,
            changed=kwargs.pop("changed", []),
            invalidated_cache=kwargs.pop("invalidated", 0),
            questions=kwargs.pop("questions", []),
            memo=kwargs.pop("memo", ""),
            analysis=kwargs.pop("analysis", {}),
            verification=kwargs.pop("verification", {}),
            tools=kwargs.pop("tools", {}),
            conflicts=kwargs.pop("conflicts", []),
            claims=kwargs.pop("claims", []),
            route=kwargs.pop("route", {}),
            coverage=kwargs.pop("coverage", {}),
            chain=kwargs.pop("chain", []),
            voi=kwargs.pop("voi", {}),
            metrics={**kwargs.pop("metrics", {}),
                     **self._usage_delta(),
                     "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)},
            trace=trace,
        )
        self.store.log_trace(state.session, turn, result.to_dict())
        return result

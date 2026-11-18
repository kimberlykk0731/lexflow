"""The consultation agent: intake → sufficiency gate → research → memo → verify."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date

from .config import Budget, LLMConfig
from .corpus import StatuteCorpus
from .elements import ElementSchema, Field
from .extract import Extractor
from .llm import BaseLLM, build_llm
from .memory import CaseState, MemoryStore
from .memo import MemoBuilder
from .rules import Analysis, _cite_short
from .tools import BudgetExceeded, ToolBox
from .verify import Verifier


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

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _fmt_fact(key: str, value) -> str:
    if isinstance(value, float):
        return f"{value:,.0f}"
    return str(value)


class ConsultationAgent:
    """A rule-controlled, LLM-assisted legal consultation agent.

    Control flow is deterministic so that ablations isolate one mechanism at a
    time.  The model is used for fact extraction and for a short plain-language
    explanation; conclusions and citations come from the rule layer.
    """

    def __init__(self, corpus: StatuteCorpus, schema: ElementSchema,
                 store: MemoryStore, llm: BaseLLM | None = None,
                 budget: Budget | None = None,
                 use_gate: bool = True, use_verify: bool = True,
                 use_repair: bool = True, use_memory: bool = True,
                 use_cache: bool = True, use_revision: bool = True,
                 today: str | None = None):
        self.corpus = corpus
        self.schema = schema
        self.store = store
        self.llm = llm or build_llm(LLMConfig())
        self.budget = budget or Budget()
        self.extractor = Extractor(schema, self.llm)
        self.memo_builder = MemoBuilder(corpus)
        self.verifier = Verifier(corpus)
        self.use_gate = use_gate
        self.use_verify = use_verify
        self.use_repair = use_repair
        self.use_memory = use_memory
        self.use_cache = use_cache
        self.use_revision = use_revision
        self.today = today or date.today().isoformat()
        self.turn_no = 0
        self.note_usage = {"prompt": 0, "completion": 0, "calls": 0}
        self._turn_usage_start = {"prompt": 0, "completion": 0, "calls": 0}

    # ------------------------------------------------------------- public
    def handle(self, session: str, text: str, document: str | None = None,
               force_memo: bool = False, case_type: str | None = None) -> TurnResult:
        started = time.perf_counter()
        self._turn_usage_start = self._usage_now()
        state = self.store.load(session) if self.use_memory else CaseState(session)
        if case_type:
            state.case_type = case_type
        self.turn_no += 1
        turn = self.turn_no
        trace: list[dict] = [{"node": "input", "text": text},
                             {"node": "session_load", "revision": state.revision,
                              "facts": len(state.facts)}]

        # 1) intake -------------------------------------------------------
        if not state.case_type:
            ranked = self.schema.classify(text)
            state.case_type = ranked[0][0] if ranked and ranked[0][1] > 0 else "labor_dismissal"
        case_type = state.case_type
        self.store.log_turn(session, turn, "user", text, {"case_type": case_type})
        extracted = self.extractor.extract(text, state.values(), case_type)
        if extracted["case_type"] != case_type and not state.facts:
            case_type = extracted["case_type"]
            state.case_type = case_type
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
            field = self.schema.field(case_type, key)
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
                key, value,
                status="user_stated",
                source="user",
                turn=turn,
                overwrite=True,
                precision=extracted.get("precision", {}).get(key, "day"))
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

        # optional document intake
        if document:
            doc = self._read_document(state, case_type, document, turn)
            changed.extend(doc)
            trace.append({"node": "document_intake", "facts": doc})

        # 2) sufficiency gate --------------------------------------------
        missing = self._missing(case_type, state)
        asked_now: list[Field] = []
        if self.use_gate and missing and not force_memo:
            candidates = [f for f in missing if state.ask_counts.get(f.key, 0) < 2]
            candidates.sort(key=lambda f: (state.ask_counts.get(f.key, 0), -f.priority))
            asked_now = candidates[:2]
            if asked_now and len(state.asked) < self.budget.max_questions:
                for f in asked_now:
                    state.asked.append(f.key)
                    state.ask_counts[f.key] = state.ask_counts.get(f.key, 0) + 1
                reply = self._ask_reply(missing, asked_now, state, changed, conflicts)
                trace.append({"node": "gate", "decision": "ask",
                              "missing": [f.key for f in missing],
                              "asked": [f.key for f in asked_now]})
                return self._finish(
                    state, turn, "asked", reply, trace, started,
                    questions=[self._q(f) for f in asked_now], changed=changed,
                    invalidated=invalidated, conflicts=conflicts)
            trace.append({"node": "gate", "decision": "answer_with_gaps",
                          "missing": [f.key for f in missing],
                          "reason": "question budget exhausted or forced"})
        elif missing:
            trace.append({"node": "gate", "decision": "skip_gate",
                          "missing": [f.key for f in missing]})
        else:
            trace.append({"node": "gate", "decision": "ready", "missing": []})

        # 3) research -----------------------------------------------------
        toolbox = ToolBox(self.corpus, self.store, state, self.budget)
        facts = {k: v for k, v in state.values().items() if v not in ("不清楚", "记不清")}
        critical_keys = [f.key for f in self.schema.fields(case_type)
                         if self.schema.is_critical(f, state.values(), case_type)]
        research: dict = {}
        try:
            if not self.use_revision and state.last_analysis:
                analysis = self._analysis_from_dict(state.last_analysis)
                trace.append({"node": "analysis_reused", "from_revision": state.revision - 1})
                res = {"evidence_ids": [], "cached": True}
            else:
                res = toolbox.call("analyse", {"case_type": case_type, "facts": facts,
                                               "today": self.today,
                                               "revision": state.revision},
                                   deps=[k for k in critical_keys])
                if not res.get("ok"):
                    raise RuntimeError(res.get("error", "analysis failed"))
                analysis = self._analysis_from_dict(res["analysis"])
                state.last_analysis = analysis.to_dict()
            research["analysis_evidence"] = res.get("evidence_ids", [])
            research["analysis_cached"] = res.get("cached", False)
            trace.append({"node": "tool:analyse", "cached": res.get("cached", False),
                          "findings": len(analysis.findings)})

            # Retrieval check: would the cited articles be retrieved for the
            # issues the analysis raises?  Diagnostic, not a correctness claim.
            retrieval_hits = 0
            for finding in analysis.findings:
                query = finding.issue + " " + finding.conclusion[:40]
                r = toolbox.call("search_statute",
                                 {"query": query, "as_of": analysis.as_of or None,
                                  "law_hints": self.schema.law_hints(case_type), "k": 5},
                                 deps=[])
                ids = [h["id"] for h in r.get("results", [])]
                hit = any(c in ids for c in finding.cites)
                retrieval_hits += 1 if hit else 0
                research.setdefault("retrieval", []).append(
                    {"finding": finding.id, "top": ids[:3], "cited": finding.cites,
                     "hit": hit})
            research["retrieval_support"] = (
                round(retrieval_hits / len(analysis.findings), 4) if analysis.findings else 0.0)

            # Make sure every cited article is materialised as evidence.
            for aid in dict.fromkeys(c for f in analysis.findings for c in f.cites):
                toolbox.call("get_article", {"article_id": aid}, deps=[])
        except BudgetExceeded as exc:
            trace.append({"node": "budget", "error": str(exc)})
            analysis = Analysis(case_type=case_type, as_of=state.value("dismiss_date")
                                or state.value("accident_date") or "",
                                headline="工具预算已用完，无法完成检索。", findings=[],
                                gaps=[str(exc)], assumptions=[])
        except Exception as exc:  # keep the consultation alive
            trace.append({"node": "error", "error": f"{type(exc).__name__}: {exc}"})
            analysis = Analysis(case_type=case_type, as_of="", headline="分析阶段出错。",
                                findings=[], gaps=[f"{type(exc).__name__}: {exc}"],
                                assumptions=[])

        # record missing critical facts as explicit gaps
        still_missing = self.schema.missing(case_type, state.values())
        if still_missing:
            analysis.gaps.insert(0, "以下关键事实尚未取得，结论只能在有限范围内成立："
                                + "、".join(f.label for f in still_missing))
        month_dates = [f.label for f in self.schema.fields(case_type)
                       if f.type == "date" and state.facts.get(f.key)
                       and state.facts[f.key].precision == "month"]
        if month_dates:
            analysis.gaps.insert(1, "以下日期只精确到月（" + "、".join(month_dates)
                                + "），可能影响时效与年限计算。")
        # 4) verify + bounded repair -------------------------------------
        verification = self.verifier.verify(analysis, state)
        if self.use_verify and verification["defects"] and self.use_repair:
            repaired = self._repair(analysis, verification, state)
            if repaired:
                verification = self.verifier.verify(analysis, state)
                trace.append({"node": "repair", "applied": repaired,
                              "defects_left": len(verification["defects"])})
        trace.append({"node": "verify", "support_rate": verification["support_rate"],
                      "defects": verification["defects"]})

        # 5) memo ---------------------------------------------------------
        llm_note = self._llm_note(analysis) if self.llm.enabled else None
        memo = self.memo_builder.render(analysis, state, verification, llm_note)
        reply = self._answer_reply(analysis, state, verification, changed)
        trace.append({"node": "memo", "chars": len(memo)})

        if conflicts:
            analysis.gaps.append("事实冲突：" + "；".join(
                f"{c['key']} 的材料记载为 {c['documented']}，您说的是 {c['user_said']}"
                for c in conflicts) + "。请核对原件后确认。")
        result = self._finish(state, turn, "answered", reply, trace, started,
                              memo=memo, analysis=analysis.to_dict(),
                              verification=verification, changed=changed,
                              invalidated=invalidated, conflicts=conflicts,
                              tools=toolbox.summary(),
                              metrics={"retrieval_support": research.get("retrieval_support", 0.0),
                                       "cached_tools": toolbox.n_cached,
                                       "executed_tools": toolbox.n_executed})
        return result

    def _missing(self, case_type: str, state: CaseState) -> list[Field]:
        missing = self.schema.missing(case_type, state.values())
        for f in self.schema.fields(case_type):
            if not self.schema.is_critical(f, state.values(), case_type):
                continue
            fact = state.facts.get(f.key)
            if (fact is not None and fact.precision == "month" and f.type == "date"
                    and f not in missing and state.ask_counts.get(f.key, 0) == 0):
                missing.append(f)
        return missing

    # ------------------------------------------------------------- intake
    def _read_document(self, state: CaseState, case_type: str, text: str, turn: int) -> list[str]:
        changed: list[str] = []
        extracted = self.extractor.extract(text, state.values(), case_type)
        for key, value in extracted["facts"].items():
            ok, keys = state.set_fact(key, value, status="documentary",
                                      source="document", turn=turn,
                                      precision=extracted.get("precision", {}).get(key, "day"))
            if ok:
                changed.extend(keys)
                self.store.log_fact(state, state.facts[key])
        return changed

    # ------------------------------------------------------------- replies
    def _q(self, f: Field) -> dict:
        return {"key": f.key, "label": f.label, "question": f.question, "why": f.why}

    def _ask_reply(self, missing: list[Field], asked: list[Field], state: CaseState,
                   changed: list[str] | None = None,
                   conflicts: list[dict] | None = None) -> str:
        lead = {
            "labor_dismissal": "在判断解除是否合法、能拿多少赔偿之前，我需要先确认几个会直接影响结论的事实。",
            "tort_injury": "在判断责任和赔偿范围之前，我需要先确认几个会直接影响适用标准的事实。",
        }.get(state.case_type, "为了给出负责任的结论，我需要先确认几个事实。")
        lines = []
        ack = self._ack(state, changed or [])
        if ack:
            lines += [ack, ""]
        if conflicts:
            parts = []
            for c in conflicts:
                f = self.schema.field(state.case_type, c["key"])
                parts.append(f"{f.label if f else c['key']} 的材料记载为 "
                             f"{c['documented']}，您说的是 {c['user_said']}")
            lines += ["⚠️ " + "；".join(parts) + "。我先保留材料记载，请核对原件后再确认。", ""]
        lines += [lead, ""]
        for i, f in enumerate(asked, 1):
            lines.append(f"{i}. {f.question}")
            if f.why:
                lines.append(f"   （为什么问：{f.why}）")
        remaining = [f for f in missing if f not in asked]
        if remaining:
            lines.append("")
            lines.append(f"另外还有 {len(remaining)} 项信息待补充，可以稍后再说。")
        lines.append("")
        lines.append("您可以直接用大白话回答，不用管法律术语。")
        return "\n".join(lines)

    def _ack(self, state: CaseState, changed: list[str]) -> str:
        parts = []
        for key in dict.fromkeys(changed):
            f = self.schema.field(state.case_type, key)
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
        lines += ["根据目前记录的事实，初步判断如下：", "", analysis.headline]
        if analysis.findings:
            main = analysis.findings[0]
            lines += ["", f"最关键的争点是「{main.issue}」：{main.conclusion}"]
        high = [f for f in analysis.findings if f.risk == "高"]
        if high:
            lines += ["", "**风险提示**：" + "；".join(f.issue for f in high)]
        if analysis.gaps:
            lines += ["", "**尚不能确定**："]
            lines += [f"- {g}" for g in analysis.gaps]
        if verification.get("defects"):
            lines += ["", f"（自动核验发现 {len(verification['defects'])} 处需要人工复核的地方，见备忘录。）"]
        lines += ["", "完整的备忘录（事实状态、争点依据、下一步材料清单）已生成。"]
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
                         for f in analysis.findings],
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
            metrics={**kwargs.pop("metrics", {}),
                     **self._usage_delta(),
                     "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)},
            trace=trace,
        )
        self.store.log_trace(state.session, turn, result.to_dict())
        return result

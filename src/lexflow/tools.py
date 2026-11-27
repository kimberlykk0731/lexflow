"""Tool layer: statute search, version lookup, arithmetic and rule analysis.

Every call is cached with an explicit fact-dependency list so that a later fact
correction invalidates exactly the results that depended on it.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from . import rules
from .config import Budget
from .corpus import StatuteCorpus
from .memory import CaseState, MemoryStore


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class ToolCall:
    name: str
    args: dict
    cached: bool
    ok: bool
    elapsed_ms: float
    evidence_ids: list[str]
    error: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ToolBox:
    def __init__(self, corpus: StatuteCorpus, store: MemoryStore, state: CaseState,
                 budget: Budget | None = None):
        self.corpus = corpus
        self.store = store
        self.state = state
        self.budget = budget or Budget()
        self.calls: list[ToolCall] = []
        self.n_executed = 0
        self.n_cached = 0

    def call(self, name: str, args: dict, deps: list[str] | None = None) -> dict:
        deps = deps or []
        key = self.store.cache_key(name, args, deps, self.state)
        started = time.perf_counter()
        cached = self.store.cache_get(key, self.state)
        if cached is not None:
            self.n_cached += 1
            self.calls.append(ToolCall(name, args, True, True, 0.0,
                                       cached.get("evidence_ids", [])))
            return {**cached, "cached": True}

        if self.n_executed >= self.budget.max_tool_calls:
            raise BudgetExceeded(f"tool budget exhausted ({self.budget.max_tool_calls})")
        try:
            result = self._dispatch(name, args)
        except Exception as exc:  # a failing tool must not crash the consultation
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            self.calls.append(ToolCall(name, args, False, False, elapsed, [], str(exc)))
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "cached": False}
        self.n_executed += 1
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        result["cached"] = False
        self.store.cache_set(key, name, result, deps, self.state,
                             ttl=self.budget.cache_ttl_seconds)
        self.calls.append(ToolCall(name, args, False, True, elapsed,
                                   result.get("evidence_ids", [])))
        return result

    def _dispatch(self, name: str, args: dict) -> dict:
        if name == "search_statute":
            return self._search_statute(**args)
        if name == "get_article":
            return self._get_article(**args)
        if name == "check_limitation":
            return self._check_limitation(**args)
        if name == "compute_compensation":
            return self._compute_compensation(**args)
        if name == "analyse":
            return self._analyse(**args)
        if name == "analyse_many":
            return self._analyse_many(**args)
        if name == "read_document":
            return self._read_document(**args)
        if name == "statute_versions":
            return self._statute_versions(**args)
        raise ValueError(f"unknown tool: {name}")

    # ------------------------------------------------------------- tools
    def _search_statute(self, query: str, as_of: str | None = None,
                        law_hints: list[str] | None = None, k: int = 5) -> dict:
        hits = self.corpus.search(query, as_of=as_of, law_ids=law_hints, k=k)
        return {"ok": True, "query": query, "as_of": as_of,
                "results": hits, "evidence_ids": [h["id"] for h in hits]}

    def _get_article(self, article_id: str) -> dict:
        art = self.corpus.get(article_id)
        if not art:
            return {"ok": False, "error": f"article not found: {article_id}"}
        return {"ok": True, "article": art.to_dict(), "evidence_ids": [art.id]}

    def _statute_versions(self, law_id: str, article_no: str) -> dict:
        versions = self.corpus.versions(law_id, article_no)
        return {"ok": True, "versions": [v.to_dict() for v in versions],
                "evidence_ids": [v.id for v in versions]}

    def _check_limitation(self, case_type: str, anchor: str, today: str | None = None) -> dict:
        res = rules.check_limitation(case_type, anchor, today)
        return {"ok": res.get("ok", False), "data": res,
                "evidence_ids": [res["basis"]] if res.get("basis") else []}

    def _compute_compensation(self, facts: dict, pay_type: str = "N",
                              extra_notice: bool = False) -> dict:
        res = rules.compute_compensation(facts, pay_type, extra_notice)
        return {"ok": res.get("ok", False), "data": res,
                "evidence_ids": res.get("cites", [])}

    def _analyse(self, case_type: str, facts: dict, today: str | None = None,
                 revision: int = 0) -> dict:
        analysis = rules.analyse(case_type, facts, today, revision)
        cites: list[str] = []
        for f in analysis.findings:
            cites.extend(f.cites)
        return {"ok": True, "analysis": analysis.to_dict(),
                "evidence_ids": list(dict.fromkeys(cites))}

    def _analyse_many(self, claims: list[str], facts: dict, today: str | None = None,
                      revision: int = 0) -> dict:
        analysis = rules.analyse_many(claims, facts, today, revision)
        cites: list[str] = []
        for f in analysis.findings:
            cites.extend(f.cites)
        return {"ok": True, "analysis": analysis.to_dict(),
                "evidence_ids": list(dict.fromkeys(cites))}

    def _read_document(self, text: str) -> dict:
        dates = re.findall(r"(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]?\s*(\d{1,2})?", text)
        amounts = re.findall(r"([\d,，]+(?:\.\d+)?)\s*元", text)
        keywords = [k for k in ("解除", "辞退", "违纪", "规章制度", "公示", "工会", "赔偿",
                                "补偿", "仲裁", "保险", "伤残", "事故") if k in text]
        return {"ok": True, "dates": dates, "amounts": amounts,
                "keywords": keywords, "evidence_ids": []}

    # ------------------------------------------------------------- summary
    def summary(self) -> dict:
        return {
            "executed": self.n_executed,
            "cached": self.n_cached,
            "total": self.n_executed + self.n_cached,
            "calls": [c.to_dict() for c in self.calls],
        }

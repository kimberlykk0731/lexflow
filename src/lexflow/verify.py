"""Claim-to-evidence verification.

The verifier is deliberately mechanical: it can prove that an article exists,
that it was in force on the relevant date, that a quoted sentence occurs in the
article, and that the facts a conclusion rests on are still current.  It cannot
prove that a legal argument is correct, and the memo says so.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .corpus import StatuteCorpus
from .memory import CaseState
from .rules import Analysis


@dataclass
class Defect:
    code: str
    claim_id: str
    detail: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _norm(text: str) -> str:
    text = re.sub(r"[\s，。；：、（）()“”\"'《》,.;:!?！？]", "", text or "")
    return text


def _numbers(text: str) -> list[float]:
    found = []
    for m in re.finditer(r"-?\d[\d,]*(?:\.\d+)?", text or ""):
        try:
            found.append(float(m.group(0).replace(",", "")))
        except ValueError:
            continue
    return found


class Verifier:
    def __init__(self, corpus: StatuteCorpus):
        self.corpus = corpus

    def verify(self, analysis: Analysis, state: CaseState) -> dict:
        as_of = analysis.as_of or None
        analysis_rev = int(analysis.metadata.get("state_revision", state.revision))
        defects: list[Defect] = []
        supported = 0
        checked = 0
        for finding in analysis.findings:
            checked += 1
            ok = True
            cites = [c for f in [finding] for c in f.cites]
            if not cites and finding.id != "F_NATURE":
                defects.append(Defect("MISSING_SOURCE", finding.id, "结论没有任何法条依据"))
                ok = False
            for aid in cites:
                art = self.corpus.get(aid)
                if art is None:
                    defects.append(Defect("UNKNOWN_SOURCE", finding.id, f"引用的法条不在语料库中：{aid}"))
                    ok = False
                    continue
                if as_of and not self.corpus.is_valid(art, as_of):
                    defects.append(Defect(
                        "VERSION_NOT_IN_FORCE", finding.id,
                        f"{art.citation} 在 {as_of} 未生效（有效期 {art.valid_from} ~ {art.valid_to}）"))
                    ok = False
                if finding.quote and _norm(finding.quote) not in _norm(art.text):
                    defects.append(Defect(
                        "QUOTE_MISMATCH", finding.id,
                        f"引文未在 {art.citation} 原文中找到：{finding.quote[:30]}"))
                    ok = False
            for dep in finding.depends:
                fact = state.facts.get(dep)
                if fact is None:
                    defects.append(Defect("MISSING_DEPENDENCY", finding.id,
                                          f"结论依赖的事实不存在或未采集：{dep}"))
                    ok = False
                elif fact.revision > analysis_rev:
                    # The fact changed after this analysis was built.
                    defects.append(Defect("SUPERSEDED_FACT", finding.id,
                                          f"结论所依据的 {dep} 在分析之后被更正（v{analysis_rev} → "
                                          f"v{fact.revision}），需重新计算"))
                    ok = False
            if finding.id == "F_COMPENSATION":
                meta = analysis.metadata.get("compensation", {})
                amount = meta.get("amount") if meta.get("ok") else None
                if amount is not None:
                    claimed = re.search(r"约(?:为)?\s*([\d,]+(?:\.\d+)?)\s*元",
                                        finding.conclusion)
                    if claimed:
                        value = float(claimed.group(1).replace(",", ""))
                        matched = abs(value - amount) <= 1
                    else:
                        matched = any(abs(n - amount) <= 1
                                      for n in _numbers(finding.conclusion))
                    if not matched:
                        defects.append(Defect("UNVERIFIED_NUMBER", finding.id,
                                              f"结论中的金额与计算结果 {amount:.0f} 不一致"))
                        ok = False
            supported += 1 if ok else 0
        return {
            "checked": checked, "supported": supported,
            "support_rate": round(supported / checked, 4) if checked else 0.0,
            "defects": [d.to_dict() for d in defects],
        }


def defect_codes(result: dict) -> list[str]:
    return [d["code"] for d in result.get("defects", [])]

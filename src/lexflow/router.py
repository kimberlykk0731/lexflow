"""Matter/claim routing.

The old agent classified a message by counting aliases and then **fell back to
``labor_dismissal``** when nothing matched.  That is why a question about a
traffic accident could be answered with a labour-arbitration questionnaire.

This router never defaults to a substantive area.  It returns one of four
actions:

* ``proceed``      — a matter/claim is clear enough to continue;
* ``clarify``      — no reliable signal; ask which kind of problem this is;
* ``out_of_scope`` — a different legal domain was detected; say so honestly;
* ``switch``       — the user moved to a different matter.

Labour is deliberately multi-label: one message can raise dismissal + unpaid
wages + overtime, and the agent will run all of those claims together.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .elements import ElementSchema
from .llm import BaseLLM, extract_json


@dataclass
class Route:
    matter: str = ""
    claims: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    action: str = "clarify"          # proceed | clarify | out_of_scope | switch
    out_of_scope: str = ""
    reply: str = ""
    note: str = ""
    source: str = "rules"

    def to_dict(self) -> dict:
        return {
            "matter": self.matter, "claims": self.claims,
            "confidence": round(self.confidence, 3), "evidence": self.evidence,
            "alternatives": [(m, round(s, 2)) for m, s in self.alternatives],
            "action": self.action, "out_of_scope": self.out_of_scope,
            "note": self.note, "source": self.source,
        }


SWITCH_MARKERS = ["不是劳动", "不是劳动争议", "换个问题", "另外一件事", "还有个事",
                  "不是这个", "我说的是", "其实是", "搞错了", "重新说"]
LABOR_WEAK = ["公司", "老板", "上班", "员工", "同事", "工位", "打卡", "入职", "离职", "用工"]

REGEX_ALIASES = {
    "labor_wage": [r"欠.{0,8}工资", r"拖.{0,8}工资", r"工资.{0,6}(没发|不发|未发|少发)"],
    "labor_overtime": [r"天天加班", r"经常加班", r"周末.{0,4}上班"],
    "labor_dismissal": [r"被.{0,6}(辞退|开除|裁)", r"让.{0,6}(走人|离职)", r"(?:我|自己|主动)辞职"],
    "labor_maternity": [r"孕期", r"生育保护"],
    "labor_work_injury": [r"上班.{0,6}(受伤|摔|伤)", r"干活.{0,6}(受伤|摔)"],
    "labor_double_pay": [r"(没|未).{0,4}签.{0,4}合同"],
    "labor_social_insurance": [r"(没|未).{0,4}(缴|交).{0,4}社保"],
}

COVERED = (
    "辞退/解除、欠薪、加班费、未签合同二倍工资、工伤、社保公积金、年休假、"
    "竞业限制、孕期产期哺乳期、劳务派遣/外包/新业态、合同试用期、仲裁程序"
)


class MatterRouter:
    def __init__(self, schema: ElementSchema, llm: BaseLLM | None = None):
        self.schema = schema
        self.llm = llm

    # ------------------------------------------------------------------ main
    def route(self, text: str, state=None) -> Route:
        text = (text or "").strip()
        if not text:
            return Route(action="clarify", reply=self._clarify_reply())

        claim_scores, hits = self._score_claims(text)
        oos_scores = self._score_out_of_scope(text)
        labor_score = sum(s for c, s in claim_scores.items()
                          if self.schema.claims.get(c, {}).get("matter") == "labor")
        tort_score = sum(s for c, s in claim_scores.items()
                         if self.schema.claims.get(c, {}).get("matter") == "tort")
        weak_labor = sum(1 for k in LABOR_WEAK if k in text)
        labor_score += weak_labor * 0.5

        top_oos, top_oos_score = (max(oos_scores.items(), key=lambda x: x[1])
                                  if oos_scores else ("", 0.0))

        # 1) a different legal domain clearly dominates -> refuse, don't guess
        if top_oos_score >= 2 and top_oos_score > max(labor_score, tort_score) + 1:
            label = self.schema.out_of_scope.get(top_oos, {}).get("label", top_oos)
            return Route(
                action="out_of_scope", out_of_scope=top_oos, confidence=0.85,
                evidence=[k for k in self.schema.out_of_scope[top_oos]["keywords"]
                          if k in text],
                alternatives=[(top_oos, top_oos_score)],
                reply=self._out_of_scope_reply(label),
            )

        # A labelled answer or correction remains in its consultation. A generic
        # word such as "伤残" or "劳动合同" must not start a different claim.
        if state is not None and getattr(state, "claims", None):
            new_topic = any(marker in text for marker in ["不是劳动", "换个问题", "另外一件事", "不是这个", "重新说",
                "另外", "还有个", "还涉及", "还想", "还要", "顺便", "新问题", "我想咨询"])
            labels = [f.label for f in self.schema.fields(state.claims)]
            labelled = any(len(label) >= 3 and label in text for label in labels)
            labelled = labelled or ("contract_signed" in
                {f.key for f in self.schema.fields(state.claims)} and
                bool(re.search(r"书面劳动合同方面|合同签了但没给我", text)))
            if labelled and not new_topic:
                return Route(matter=state.matter, claims=list(state.claims),
                             confidence=0.8, action="proceed", source="context",
                             note="按当前咨询记录回答或更正事实")

        # 2) explicit correction / topic switch
        switch = any(m in text for m in SWITCH_MARKERS)
        current_matter = getattr(state, "matter", "") if state else ""

        # 3) a short answer inside an ongoing consultation is not a new topic
        if not claim_scores and top_oos_score < 3:
            if state is not None and getattr(state, "claims", None):
                return Route(matter=state.matter, claims=list(state.claims),
                             confidence=0.6, action="proceed", source="context",
                             note="延续当前咨询")
            if self.llm and self.llm.enabled:
                llm_route = self._llm_route(text)
                if llm_route and llm_route.action != "clarify":
                    return self._apply_context(llm_route, state)
            return Route(action="clarify", reply=self._clarify_reply(), confidence=0.0,
                         alternatives=self._alternatives(claim_scores, oos_scores))

        matter = "labor" if labor_score >= tort_score else "tort"
        # Work injury caused by a commuting traffic accident is a labour matter
        # first; note the tort claim instead of silently dropping it.
        note = ""
        if matter == "labor" and tort_score > 0 and "labor_work_injury" in claim_scores:
            note = "您同时提到交通事故和工伤可能，先按工伤处理；交通事故侵权可以另行主张，注意医疗费不重复受偿。"
        if top_oos_score >= 2 and top_oos:
            label = self.schema.out_of_scope.get(top_oos, {}).get("label", top_oos)
            note = (note + " " if note else "") + f"另外提到的「{label}」不在本版本覆盖范围，我只能就劳动/交通部分作答。"

        claims = [c for c, s in sorted(claim_scores.items(), key=lambda x: -x[1])
                  if s > 0 and self.schema.claims.get(c, {}).get("matter") == matter]
        if not claims:
            # A weak "公司/老板" mention is not enough to pick a claim.  Ask
            # which labour issue it is instead of defaulting to dismissal.
            return Route(action="clarify", reply=self._labor_clarify_reply(),
                         confidence=0.2, evidence=hits,
                         alternatives=self._alternatives(claim_scores, oos_scores))
        # keep at most 4 claims in one pass; the rest can be added next turn
        claims = claims[:4]

        total = labor_score + tort_score + 1
        confidence = max(labor_score, tort_score) / total
        action = "proceed"
        if current_matter and matter != current_matter:
            action = "switch" if switch or confidence >= 0.6 else "proceed"
        if confidence < 0.25 and not switch:
            return Route(action="clarify", reply=self._clarify_reply(),
                         confidence=confidence, evidence=hits,
                         alternatives=self._alternatives(claim_scores, oos_scores))

        return Route(matter=matter, claims=claims, confidence=confidence,
                     evidence=hits[:6], action=action, note=note,
                     alternatives=self._alternatives(claim_scores, oos_scores))

    # --------------------------------------------------------------- scoring
    def _score_claims(self, text: str) -> tuple[dict[str, float], list[str]]:
        scores: dict[str, float] = {}
        hits: list[str] = []
        for cid, spec in self.schema.claims.items():
            score = 0.0
            for alias in spec.get("aliases", []):
                if alias and alias in text:
                    # longer, more specific phrases weigh more
                    score += 3.0 if len(alias) >= 4 else 2.0
                    hits.append(alias)
            for pattern in REGEX_ALIASES.get(cid, []):
                if re.search(pattern, text):
                    score += 2.5
                    hits.append(pattern)
            if score:
                scores[cid] = score
        if ("labor_dismissal" in scores and "labor_contract" in scores
                and re.search(r"不续签|合同.{0,4}到期|解除劳动合同|辞职", text)
                and not re.search(r"试用期|调岗|降薪|单方变更|无固定期限", text)):
            scores.pop("labor_contract")
        return scores, list(dict.fromkeys(hits))

    def _score_out_of_scope(self, text: str) -> dict[str, float]:
        scores: dict[str, float] = {}
        for key, spec in self.schema.out_of_scope.items():
            score = sum(3.0 if len(k) >= 3 else 2.0 for k in spec.get("keywords", [])
                        if k in text)
            if score:
                scores[key] = score
        return scores

    def _alternatives(self, claim_scores: dict[str, float],
                      oos_scores: dict[str, float]) -> list[tuple[str, float]]:
        alts = [(self.schema.label(c), s) for c, s in claim_scores.items()]
        alts += [(self.schema.out_of_scope.get(k, {}).get("label", k), s)
                 for k, s in oos_scores.items()]
        return sorted(alts, key=lambda x: -x[1])[:5]

    # -------------------------------------------------------------- replies
    def clarify_reply(self) -> str:
        return self._clarify_reply()

    def _clarify_reply(self) -> str:
        return (
            "我想先确认一下您遇到的是哪类问题，避免答错方向：\n\n"
            "1. **劳动用工**：辞退/裁员、欠薪、加班费、未签合同、工伤、社保、年假、"
            "竞业限制、孕期产期哺乳期、派遣/外包/新业态等；\n"
            "2. **交通事故/人身损害**：责任认定、伤残、保险、赔偿项目；\n"
            "3. **其他**：婚姻家事、借贷、房产、合同、刑事等（当前版本暂不覆盖）。\n\n"
            "您可以直接用大白话说一句“发生了什么、对方是谁、您想要什么”。"
        )

    def _labor_clarify_reply(self) -> str:
        return (
            "听起来是和公司/工作有关，但具体是哪一类问题？不同请求权的路径差别很大：\n\n"
            "1. 被辞退/裁员/被迫离职（N、N+1、2N）；\n"
            "2. 欠薪、提成/年终奖、降薪；\n"
            "3. 加班费、996/大小周；\n"
            "4. 没签书面合同、二倍工资；\n"
            "5. 工伤、职业病；\n"
            "6. 社保/公积金断缴、补缴；\n"
            "7. 年假、竞业限制、孕期产期哺乳期；\n"
            "8. 劳务派遣/外包/骑手/主播等用工形式；\n"
            "9. 只是想问劳动仲裁/诉讼怎么走。\n\n"
            "您说一句“发生了什么、您想要什么”就可以，不用选编号。"
        )

    def _out_of_scope_reply(self, label: str) -> str:
        return (
            f"您描述的问题更像**{label}**，不在当前版本覆盖的范围内，我不想用劳动仲裁的"
            f"模板硬套，那样会误导您。\n\n"
            f"本版本目前专注：{COVERED}；以及交通事故人身损害赔偿。\n\n"
            "如果这件事其实和劳动用工有关（比如工伤、欠薪、解除），您可以补充一句"
            "“我是在工作中/因为工作遇到的”，我再按劳动纠纷来分析。"
        )

    # ------------------------------------------------------------- context
    def _apply_context(self, route: Route, state) -> Route:
        current = getattr(state, "matter", "") if state else ""
        if current and route.matter and route.matter != current:
            route.action = "switch"
        return route

    # ------------------------------------------------------------------ LLM
    def _llm_route(self, text: str) -> Route | None:
        """Only used to disambiguate when the rule layer has no signal."""
        taxonomy = {
            cid: {"label": spec["label"], "matter": spec.get("matter", ""),
                  "examples": spec.get("aliases", [])[:8]}
            for cid, spec in self.schema.claims.items()
        }
        oos = {k: v for k, v in self.schema.out_of_scope.items()}
        res = self.llm.complete([
            {"role": "system", "content": (
                "你是法律咨询的分诊模块。只判断问题属于哪个领域/哪些请求权，不回答法律问题。"
                "输出严格 JSON：{\"matter\":\"labor|tort|other|unknown\","
                "\"claims\":[\"claim_id\"],\"out_of_scope\":\"\",\"confidence\":0-1}。"
                "拿不准就 matter=unknown，不要默认劳动。")},
            {"role": "user", "content": json.dumps(
                {"text": text, "claims": taxonomy, "out_of_scope": oos},
                ensure_ascii=False)},
        ], temperature=0, max_tokens=300)
        if not res.ok:
            return None
        data = extract_json(res.text)
        if not isinstance(data, dict):
            return None
        matter = data.get("matter", "unknown")
        raw_claims = data.get("claims", [])
        claims = [c for c in raw_claims if isinstance(c, str) and c in self.schema.claims] if isinstance(raw_claims, list) else []
        if matter not in {"labor", "tort", "other"} or (not claims and matter != "other"):
            return Route(action="clarify", reply=self._clarify_reply(), source="llm")
        if matter == "other":
            oos_key = data.get("out_of_scope", "")
            label = self.schema.out_of_scope.get(oos_key, {}).get("label", "其他法律领域")
            return Route(action="out_of_scope", out_of_scope=oos_key,
                         reply=self._out_of_scope_reply(label), source="llm")
        claims = [c for c in claims if self.schema.claims[c].get("matter") == matter]
        if not claims:
            return Route(action="clarify", reply=self._clarify_reply(), source="llm")
        try:
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        return Route(matter=matter, claims=claims[:4],
                     confidence=confidence,
                     action="proceed", source="llm")

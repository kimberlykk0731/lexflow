"""Deterministic client NPC used when no client LLM is configured.

DLawBench's official client is an LLM driven by ``config/client_npc_prompt.txt``.
For an offline, reproducible run we implement the same contract with a
deterministic responder: it reads only the ``client_belief`` facts that the
official prompt puts in its system message, reveals a fact only when the
lawyer's question is on the same topic, and speaks in the persona's voice.

This is a stand-in for the official client model, not a claim that the persona
simulation is equivalent.  It is documented in docs/EXTERNAL_EVAL.md.
"""
from __future__ import annotations

import re

try:  # package import
    from .textutil import containment, dates, overlap, sentences, terms, topics_of
except ImportError:  # script import
    from textutil import containment, dates, overlap, sentences, terms, topics_of

FACT_SECTION_RE = re.compile(r"【你知道的事实】(.*?)【对话规则】", re.S)
PERSONAS = ("P_WD", "P_WS", "P_CS", "P_CD")

CLOSERS = {
    "P_WD": ["您看这些够不够？", "我这边能想起来的就这些。", "需要的话我可以再找材料。"],
    "P_WS": ["您觉得这样行吗？", "我不太懂，您帮我判断一下。", "要不要我再想想？"],
    "P_CS": ["别的我记不清了。", "大概就是这样。", "我不太想说太多。"],
    "P_CD": ["你听我说，这事没那么复杂。", "我知道的就这些。", "你按这个思路办就行。"],
}

OPENERS = {
    "P_WD": ["我想确认一下，", "按我的理解，", ""],
    "P_WS": ["这个……", "我不太确定，不过", ""],
    "P_CS": ["", "大概", ""],
    "P_CD": ["", "我跟你说，", ""],
}

FALLBACK = {
    "P_WD": "这个我手上没有材料，您具体想确认哪一点？",
    "P_WS": "这个我不太确定……您觉得重要吗？",
    "P_CS": "记不清了。",
    "P_CD": "这我不清楚，你问点有用的。",
}

# Persona behaviour beyond wording: how many facts one answer may contain and
# how strongly the question must match before the client opens up.
MAX_FACTS = {"P_WD": 2, "P_WS": 1, "P_CS": 1, "P_CD": 1}
REVEAL_THRESHOLD = {"P_WD": 0.35, "P_WS": 0.55, "P_CS": 0.90, "P_CD": 0.70}


def client_model(persona: str = "P_WD") -> str:
    return "lexflow-client-" + persona.lower().replace("_", "-")


def persona_from_model(name: str) -> str:
    lower = (name or "").strip().lower()
    for persona in PERSONAS:
        if lower == client_model(persona):
            return persona
    return "P_WD"


class ClientSimulator:
    def __init__(self, persona: str = "P_WD"):
        if persona not in PERSONAS:
            persona = "P_WD"
        self.persona = persona

    def respond(self, messages: list[dict]) -> str:
        system = ""
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content") or ""
                break

        facts = self._parse_facts(system)
        question = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                question = msg.get("content") or ""
                break

        previous = " ".join(
            msg.get("content") or "" for msg in messages if msg.get("role") == "assistant"
        )

        unrevealed = [f for f in facts if containment(terms(f), terms(previous)) < 0.55]
        if not unrevealed:
            if question:
                return "这个我刚才已经说过了。" if self.persona == "P_WD" else "说过了。"
            return FALLBACK[self.persona]

        q_topics = topics_of(question)
        scored: list[tuple[float, str, int]] = []
        for fact in unrevealed:
            shared = len(q_topics & topics_of(fact))
            lexical = overlap(terms(question), terms(fact))
            bonus = 0.7 if ("时间" in question or "什么时候" in question) and dates(fact) else 0.0
            scored.append((shared * 1.0 + lexical * 1.5 + bonus, fact, shared))
        scored.sort(reverse=True)

        best_score, best, best_shared = scored[0]
        if best_shared == 0 and best_score < REVEAL_THRESHOLD[self.persona]:
            return FALLBACK[self.persona]
        if self.persona == "P_CS" and best_score < REVEAL_THRESHOLD["P_CS"]:
            return "记不清了。"
        if self.persona == "P_CD" and best_score < REVEAL_THRESHOLD["P_CD"]:
            return "这跟我的事有关系吗？你直接说重点。"

        chosen = [best]
        # Only the cooperative persona volunteers a closely related second fact.
        for score, fact, shared in scored[1:]:
            if len(chosen) >= MAX_FACTS[self.persona]:
                break
            if shared == 0:
                continue
            if score >= max(0.9, best_score * 0.55):
                chosen.append(fact)
        return self._style(chosen, question)

    # --------------------------------------------------------------- helpers
    def _parse_facts(self, system: str) -> list[str]:
        match = FACT_SECTION_RE.search(system)
        if not match:
            return []
        facts: list[str] = []
        for line in match.group(1).splitlines():
            line = line.strip()
            if line.startswith("- "):
                facts.append(line[2:].strip())
        return facts

    def _style(self, facts: list[str], question: str) -> str:
        bodies: list[str] = []
        for fact in facts:
            parts = sentences(fact)
            body = "。".join(parts[:2]).strip("。") + "。" if parts else fact
            bodies.append(body)
        body = "另外，".join(bodies)
        opener = OPENERS[self.persona][len(question) % 3]
        closer = CLOSERS[self.persona][len(question) % len(CLOSERS[self.persona])]
        text = f"{opener}{body}"
        if not text.endswith(("。", "！", "？")):
            text += "。"
        return f"{text}{closer}"

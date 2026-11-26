"""Deterministic stand-in for DLawBench's LLM judge.

The official evaluator asks a judge model to score (a) memo rubrics / inquiry
actions and (b) a three-way fact-set comparison (discovery / accuracy /
grounding).  Without an API key we cannot call the official judge.  This module
answers the *same official prompts* with a lexical rubric matcher and returns
the *same JSON schema*, so the official ``evaluate.py`` and ``metrics.py``
formulas and denominators are used unchanged.

It is a stand-in, not a reproduction of the paper's judge.  Absolute scores are
therefore not comparable to the DLawBench leaderboard; only differences between
policies run under this same judge are meaningful.  See docs/EXTERNAL_EVAL.md.
"""
from __future__ import annotations

import json
import re

try:  # package import
    from .textutil import amounts, containment, dates, overlap, sentences, terms
except ImportError:  # script import
    from textutil import amounts, containment, dates, overlap, sentences, terms

JUDGE_MODEL = "lexflow-rubric-judge"

MEMO_HEADER = "【评估标准 — 备忘录要点】（每项 0 或 1 分）"
ACTION_HEADER = "【评估标准 — 律师问诊动作】（每项 0 或 1 分，根据对话记录判断律师是否执行了该动作）"
DIALOGUE_HEADER = "【对话记录】"
MEMO_HEADER_2 = "【备忘录内容】"
DAG_HEADER = "集合 A：案件事实"
DAG_DIALOGUE = "对话记录（律师与客户的完整问诊过程）"
DAG_MEMO = "集合 B：律师备忘录"


def is_judge_model(name: str) -> bool:
    return (name or "").strip().lower() == JUDGE_MODEL


def judge_reply(messages: list[dict]) -> str:
    prompt = "\n".join((m.get("content") or "") for m in messages)
    if MEMO_HEADER in prompt and ACTION_HEADER in prompt:
        return json.dumps(_judge_memo(prompt), ensure_ascii=False)
    if DAG_HEADER in prompt and DAG_MEMO in prompt:
        return json.dumps(_judge_dag(prompt), ensure_ascii=False)
    return json.dumps({"analysis": "unrecognised judge prompt"}, ensure_ascii=False)


# ── memo rubric / inquiry actions ─────────────────────────────────────────
def _judge_memo(prompt: str) -> dict:
    expectations = _numbered_items(prompt, MEMO_HEADER, ACTION_HEADER)
    actions = _numbered_items(prompt, ACTION_HEADER, DIALOGUE_HEADER)
    dialogue = _slice(prompt, DIALOGUE_HEADER, MEMO_HEADER_2)
    memo = _slice(prompt, MEMO_HEADER_2, "\n\n请输出 JSON", strip_tail=True)

    windows = _windows(memo)
    memo_scores = [
        1 if _best_window_containment(item, windows) >= 0.26 else 0
        for item in expectations
    ]

    lawyer_lines = [
        line.split("：", 1)[1]
        for line in dialogue.splitlines()
        if line.startswith("律师（第") and "：" in line
    ]
    action_scores = [
        1 if _best_action_overlap(item, lawyer_lines) >= 0.22 else 0
        for item in actions
    ]

    return {
        "memo_expectation_scores": memo_scores,
        "expected_action_scores": action_scores,
        "overall_quality": "Pass" if sum(memo_scores) >= max(1, len(memo_scores) // 2) else "Fail",
        "analysis": "deterministic lexical rubric matcher (offline stand-in)",
    }


# ── fact-set DAG ──────────────────────────────────────────────────────────
def _judge_dag(prompt: str) -> dict:
    facts = _parse_facts(prompt)
    dialogue = _slice(prompt, DAG_DIALOGUE, DAG_MEMO)
    memo = _slice(prompt, DAG_MEMO, "\n\n请输出 JSON", strip_tail=True)
    windows = _windows(memo)
    source_terms = terms(dialogue + " " + " ".join(
        f["client"] + " " + f["court"] for f in facts
    ))

    covered: list[str] = []
    missed: list[str] = []
    correct: list[str] = []
    incorrect: list[dict] = []
    for fact in facts:
        best, score = _best_window(fact["client"] + " " + fact["court"], windows)
        if score >= 0.30 or (best and containment(terms(best), terms(fact["court"])) >= 0.55):
            covered.append(fact["id"])
            if _contradicts(best or "", fact):
                incorrect.append({
                    "fact_id": fact["id"],
                    "memo_excerpt": (best or "")[:120],
                    "reason": "备忘录采信了客户认知中的日期/金额，与案卷事实不一致",
                })
            else:
                correct.append(fact["id"])
        else:
            missed.append(fact["id"])

    claims = _claims(memo)
    grounded: list[dict] = []
    ungrounded: list[dict] = []
    for claim in claims:
        if containment(terms(claim), source_terms) >= 0.45:
            grounded.append({"claim": claim[:160], "basis": "对话记录或案件事实"})
        else:
            ungrounded.append({"claim": claim[:160], "reason": "在案件事实和对话记录中无直接来源"})

    return {
        "discovery": {"covered": covered, "missed": missed},
        "accuracy": {"correct": correct, "incorrect": incorrect},
        "grounding": {
            "total_claims": len(claims),
            "grounded_claims": grounded,
            "ungrounded_claims": ungrounded,
        },
    }


# ── helpers ───────────────────────────────────────────────────────────────
def _slice(text: str, start_marker: str, end_marker: str, strip_tail: bool = False) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    start += len(start_marker)
    end = text.find(end_marker, start)
    body = text[start:] if end < 0 else text[start:end]
    body = body.strip("\n")
    if strip_tail:
        body = body.strip()
    return body


def _numbered_items(text: str, start_marker: str, end_marker: str) -> list[str]:
    block = _slice(text, start_marker, end_marker)
    items: list[str] = []
    for line in block.splitlines():
        match = re.match(r"\s*\d+[.、]\s*(.+?)\s*$", line)
        if match:
            items.append(match.group(1))
    return items


def _windows(text: str) -> list[str]:
    """Paragraphs, bullets and single sentences, deduplicated."""
    out: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text or ""):
        paragraph = paragraph.strip()
        if not paragraph or paragraph.startswith("#"):
            continue
        paragraph = re.sub(r"^[-•]\s*", "", paragraph)
        paragraph = re.sub(r"^\d+[.、]\s+", "", paragraph)
        if len(paragraph) >= 4:
            out.append(paragraph)
        for sentence in sentences(paragraph):
            if len(sentence) >= 6:
                out.append(sentence)
    seen: set[str] = set()
    unique = []
    for item in out:
        key = re.sub(r"\s+", "", item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _best_window(needle: str, windows: list[str]) -> tuple[str | None, float]:
    best, best_score = None, 0.0
    needle_terms = terms(needle)
    for window in windows:
        score = containment(needle_terms, terms(window))
        if score > best_score:
            best, best_score = window, score
    return best, best_score


def _best_window_containment(needle: str, windows: list[str]) -> float:
    return _best_window(needle, windows)[1]


def _best_action_overlap(needle: str, lawyer_lines: list[str]) -> float:
    """How much of a short lawyer question is subsumed by one rubric item."""
    best = 0.0
    for line in lawyer_lines:
        best = max(best, overlap(terms(line), terms(needle)))
    return best


def _parse_facts(prompt: str) -> list[dict]:
    block = _slice(prompt, DAG_HEADER, DAG_DIALOGUE)
    pattern = re.compile(
        r"事实\s*(F\d+)（([^）]*)）:\s*\n\s*客户认知:\s*(.*?)\n\s*实际情况:\s*(.*?)(?=\n\s*\n事实\s*F\d+|\Z)",
        re.S,
    )
    facts: list[dict] = []
    for match in pattern.finditer(block):
        facts.append({
            "id": match.group(1),
            "gap_type": match.group(2).strip(),
            "client": match.group(3).strip(),
            "court": match.group(4).strip().rstrip("━").strip(),
        })
    return facts


def _contradicts(window: str, fact: dict) -> bool:
    """True when the memo repeats a client-belief date/amount that the record contradicts."""
    window_dates = set(dates(window))
    court_dates = set(dates(fact["court"]))
    client_dates = set(dates(fact["client"]))
    if window_dates and court_dates and client_dates:
        if window_dates & client_dates and not (window_dates & court_dates):
            return True

    window_amounts = {re.sub(r"\s+", "", a) for a in amounts(window)}
    court_amounts = {re.sub(r"\s+", "", a) for a in amounts(fact["court"])}
    client_amounts = {re.sub(r"\s+", "", a) for a in amounts(fact["client"])}
    if window_amounts and court_amounts and client_amounts:
        if window_amounts & client_amounts and not (window_amounts & court_amounts):
            return True
    return False


def _claims(memo: str) -> list[str]:
    """Factual claims, excluding the legal-analysis and next-step sections.

    Every bullet under ``关键事实`` is a factual claim (it should be sourced).
    In the summary / risk sections only sentences with concrete numbers or dates
    count, so generic risk language is not misread as a fabricated fact.
    """
    sections = _sections(memo)
    claims: list[str] = []
    for sentence in sentences(sections.get("关键事实", "")):
        sentence = sentence.strip("-• \t")
        if len(sentence) >= 6:
            claims.append(sentence)
    for name in ("案情概要", "风险评估"):
        for sentence in sentences(sections.get(name, "")):
            sentence = sentence.strip("-• \t")
            if len(sentence) >= 6 and re.search(r"\d", sentence):
                claims.append(sentence)
    seen: set[str] = set()
    unique: list[str] = []
    for claim in claims:
        key = re.sub(r"\s+", "", claim)
        if key not in seen:
            seen.add(key)
            unique.append(claim)
    return unique


def _sections(memo: str) -> dict[str, str]:
    result: dict[str, str] = {}
    current = ""
    buffer: list[str] = []
    for line in (memo or "").splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if current:
                result[current] = "\n".join(buffer)
            current = match.group(1)
            buffer = []
            continue
        if current:
            buffer.append(line)
    if current:
        result[current] = "\n".join(buffer)
    return result

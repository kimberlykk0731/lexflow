"""Curated practice notes from courts, human-resources authorities and their
official publications.

The statute corpus answers "what is the rule"; these notes answer "what do
courts actually look at".  They are deliberately short paraphrases with a
publisher, date and link — not copies of the articles.  Court newspapers carry
copyright notices, so only facts/holdings and our own checklists are stored.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import DATA

NOTES_PATH = DATA / "knowledge" / "practice_notes.json"


@dataclass
class Note:
    id: str
    title: str
    publisher: str
    date: str
    url: str
    topics: list[str] = field(default_factory=list)
    points: list[str] = field(default_factory=list)
    caveat: str = ""
    source_type: str = "court"
    priority: int = 50

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def as_markdown(self) -> str:
        lines = [f"**{self.title}**（{self.publisher}，{self.date}）"]
        lines += [f"- {p}" for p in self.points]
        if self.caveat:
            lines.append(f"- 注意：{self.caveat}")
        lines.append(f"- 来源：[{self.url}]({self.url})")
        return "\n".join(lines)


class KnowledgeBase:
    def __init__(self, path: Path | str = NOTES_PATH):
        self.path = Path(path)
        self.notes: list[Note] = []
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.notes = [Note(**n) for n in raw.get("notes", [])]

    def for_claims(self, claims: list[str], limit: int = 4) -> list[Note]:
        scored = []
        for n in self.notes:
            overlap = len(set(n.topics) & set(claims))
            if overlap:
                scored.append((overlap * 10 + n.priority, n))
        scored.sort(key=lambda x: -x[0])
        return [n for _, n in scored[:limit]]

    def for_topic(self, topic: str, limit: int = 5) -> list[Note]:
        return [n for n in self.notes if topic in n.topics][:limit]

    def search(self, query: str, limit: int = 5) -> list[Note]:
        terms = [t for t in query.split() if t]
        scored = []
        for n in self.notes:
            text = n.title + " " + " ".join(n.points)
            score = sum(1 for t in terms if t in text)
            if score:
                scored.append((score, n))
        scored.sort(key=lambda x: -x[0])
        return [n for _, n in scored[:limit]]

    def render(self, notes: list[Note]) -> str:
        if not notes:
            return ""
        lines = ["### 实务提示（法院/人社口径）", ""]
        for n in notes:
            lines.append(n.as_markdown())
            lines.append("")
        return "\n".join(lines).strip()

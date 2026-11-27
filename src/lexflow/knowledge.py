"""Retrieval-augmented practice notes (court / MOHRSS guidance).

The statute corpus answers "what is the rule"; these notes answer "what do
courts actually look at".  The retriever is a small BM25 over *chunks* (one
point per chunk), with structured claim filters and source metadata.  It is a
lightweight RAG pipeline: query construction → chunk retrieval → grounded
passages with publisher/date/URL → memo citation.  No embedding service is
required, so the demo stays dependency-free and reproducible.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .config import DATA
from .corpus import expand_query, tokenize

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


@dataclass
class Chunk:
    id: str
    note_id: str
    text: str
    topics: list[str]
    priority: int
    is_title: bool = False


class KnowledgeBase:
    def __init__(self, path: Path | str = NOTES_PATH):
        self.path = Path(path)
        self.notes: list[Note] = []
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.notes = [Note(**n) for n in raw.get("notes", [])]
        self.chunks: list[Chunk] = []
        self._tf: list[Counter] = []
        self._df: Counter = Counter()
        self._avgdl = 0.0
        self._build_index()

    # ------------------------------------------------------------- indexing
    def _build_index(self) -> None:
        for note in self.notes:
            pieces = [note.title] + list(note.points)
            if note.caveat:
                pieces.append(note.caveat)
            for i, text in enumerate(pieces):
                self.chunks.append(Chunk(
                    id=f"{note.id}#{i}", note_id=note.id, text=text,
                    topics=note.topics, priority=note.priority,
                    is_title=(i == 0)))
                tf = Counter(tokenize(expand_query(text)))
                self._tf.append(tf)
                for term in tf:
                    self._df[term] += 1
        self._avgdl = (sum(sum(tf.values()) for tf in self._tf) / len(self._tf)
                       if self._tf else 0.0)

    # ------------------------------------------------------------ retrieval
    def retrieve(self, query: str, claims: list[str] | None = None,
                 k: int = 4) -> list[dict]:
        """Return note-level hits with matched passages and BM25 scores."""
        query = (query or "").strip()
        if not query or not self.chunks:
            return self._fallback(claims, k)
        q_tokens = tokenize(expand_query(query))
        if not q_tokens:
            return self._fallback(claims, k)
        n = len(self.chunks)
        scores: dict[str, float] = {}
        best_chunk: dict[str, tuple[float, str]] = {}
        candidates = [i for i, c in enumerate(self.chunks)
                      if not claims or set(c.topics) & set(claims)]
        if not candidates:
            candidates = list(range(n))
        for i in candidates:
            chunk = self.chunks[i]
            tf = self._tf[i]
            dl = sum(tf.values()) or 1
            score = 0.0
            for term in q_tokens:
                if term not in tf:
                    continue
                df = self._df.get(term, 0) or 1
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                freq = tf[term]
                score += idf * (freq * 2.2) / (freq + 1.2 * (0.25 + 0.75 * dl / (self._avgdl or 1)))
            if chunk.is_title:
                score *= 1.4
            score += chunk.priority / 50.0
            if score <= 0:
                continue
            scores[chunk.note_id] = scores.get(chunk.note_id, 0.0) + score
            old = best_chunk.get(chunk.note_id)
            if old is None or score > old[0]:
                best_chunk[chunk.note_id] = (score, chunk.text)

        order = sorted(scores.items(), key=lambda x: -x[1])
        if order:
            top = order[0][1]
            # keep only reasonably close hits; otherwise generic "解除/2N"
            # passages can crowd out the actually relevant note
            order = [x for x in order if x[1] >= top * 0.30][:k]
        out = []
        for note_id, score in order:
            note = next((x for x in self.notes if x.id == note_id), None)
            if not note:
                continue
            _, passage = best_chunk[note_id]
            if passage == note.title and note.points:
                passage = note.points[0]
            # return the matched point first, then the rest (deduped)
            points = [passage] + [p for p in note.points if p != passage]
            d = note.to_dict()
            d.update({"score": round(score, 3), "points": points,
                      "matched": passage})
            out.append(d)
        if len(out) < 2 and claims:
            seen = {x["id"] for x in out}
            for n in self.for_claims(claims, k):
                if n.id in seen:
                    continue
                out.append(dict(n.to_dict(), score=0.0,
                                matched=n.points[0] if n.points else ""))
                seen.add(n.id)
                if len(out) >= 2:
                    break
        return out or self._fallback(claims, k)

    def _fallback(self, claims: list[str] | None, k: int) -> list[dict]:
        notes = self.for_claims(claims or [], limit=k)
        return [dict(n.to_dict(), score=0.0, matched=n.points[0] if n.points else "")
                for n in notes]

    # --------------------------------------------------------- structured
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
        return [self._note_by_id(h["id"]) for h in self.retrieve(query, None, limit)
                if self._note_by_id(h["id"])]

    def _note_by_id(self, note_id: str) -> Note | None:
        return next((n for n in self.notes if n.id == note_id), None)

    def render(self, notes: list[Note]) -> str:
        if not notes:
            return ""
        lines = ["### 实务提示（法院/人社口径）", ""]
        for n in notes:
            lines.append(n.as_markdown())
            lines.append("")
        return "\n".join(lines).strip()

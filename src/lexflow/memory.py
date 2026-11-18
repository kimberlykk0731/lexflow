"""Persistent, versioned case memory and a dependency-aware tool cache."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .config import corpus_version


@dataclass
class Fact:
    key: str
    value: object
    status: str = "user_stated"   # user_stated | documentary | verified | unknown
    source: str = "user"
    turn: int = 0
    revision: int = 0
    superseded_by: int | None = None
    precision: str = "day"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CaseState:
    session: str
    case_type: str = ""
    facts: dict[str, Fact] = field(default_factory=dict)
    history: list[Fact] = field(default_factory=list)
    revision: int = 0
    asked: list[str] = field(default_factory=list)
    ask_counts: dict[str, int] = field(default_factory=dict)
    known_unknowns: list[str] = field(default_factory=list)
    last_analysis: dict | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # -------------------------------------------------------------- facts
    def value(self, key: str, default=None):
        f = self.facts.get(key)
        return f.value if f and f.status != "superseded" else default

    def values(self) -> dict:
        return {k: f.value for k, f in self.facts.items()
                if f.superseded_by is None and f.value not in (None, "")}

    def superseded(self) -> list[Fact]:
        return [f for f in self.history if f.superseded_by is not None]

    def set_fact(self, key: str, value, status: str = "user_stated",
                 source: str = "user", turn: int = 0, overwrite: bool = True,
                 precision: str = "day") -> tuple[bool, list[str]]:
        """Set a fact. Returns (changed, list of invalidated fact keys)."""
        if value in (None, ""):
            return False, []
        old = self.facts.get(key)
        if old is not None and str(old.value) == str(value):
            if old.status == status:
                return False, []
            # same value: never downgrade provenance
            if old.status in ("documentary", "verified") and status == "user_stated":
                return False, []
        if old is not None and not overwrite:
            return False, []
        new_rev = self.revision + 1
        if old is not None:
            old.superseded_by = new_rev
            self.history.append(old)
        self.facts[key] = Fact(key=key, value=value, status=status, source=source,
                               turn=turn, revision=new_rev, precision=precision)
        self.revision = new_rev
        self.updated_at = time.time()
        return True, [key]

    def mark_unknown(self, key: str, turn: int = 0) -> bool:
        if key in self.facts and self.facts[key].status != "unknown":
            return False
        self.facts[key] = Fact(key=key, value="不清楚", status="unknown", turn=turn,
                               revision=self.revision)
        if key not in self.known_unknowns:
            self.known_unknowns.append(key)
        return True

    # -------------------------------------------------------------- serialisation
    def to_dict(self) -> dict:
        return {
            "session": self.session, "case_type": self.case_type,
            "facts": {k: v.to_dict() for k, v in self.facts.items()},
            "history": [f.to_dict() for f in self.history],
            "revision": self.revision, "asked": self.asked,
            "ask_counts": self.ask_counts,
            "known_unknowns": self.known_unknowns,
            "last_analysis": self.last_analysis,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CaseState":
        st = cls(session=d["session"], case_type=d.get("case_type", ""),
                 revision=d.get("revision", 0), asked=d.get("asked", []),
                 ask_counts=d.get("ask_counts", {}),
                 known_unknowns=d.get("known_unknowns", []),
                 last_analysis=d.get("last_analysis"),
                 created_at=d.get("created_at", time.time()),
                 updated_at=d.get("updated_at", time.time()))
        for k, v in d.get("facts", {}).items():
            st.facts[k] = Fact(**v)
        st.history = [Fact(**f) for f in d.get("history", [])]
        return st

    def fact_table(self) -> list[dict]:
        rows = []
        for f in sorted(self.facts.values(), key=lambda x: (-x.revision, x.key)):
            rows.append({"key": f.key, "value": f.value, "status": f.status,
                         "source": f.source, "turn": f.turn,
                         "revision": f.revision,
                         "precision": f.precision,
                         "superseded_by": f.superseded_by})
        return rows


class MemoryStore:
    """SQLite-backed session store plus a tool-result cache with dependencies."""

    def __init__(self, path: str | Path = ":memory:", cache: bool = True, memory: bool = True):
        self.path = str(path)
        self.use_cache = cache
        self.use_memory = memory
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self._schema()

    def _schema(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS case_state (
            session TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at REAL);
        CREATE TABLE IF NOT EXISTS fact_log (
            session TEXT, fact_key TEXT, value TEXT, status TEXT, source TEXT,
            turn INTEGER, revision INTEGER, superseded_by INTEGER, ts REAL);
        CREATE TABLE IF NOT EXISTS tool_cache (
            key TEXT PRIMARY KEY, tool TEXT, payload TEXT, deps TEXT,
            state_revision INTEGER, expires REAL, created REAL);
        CREATE TABLE IF NOT EXISTS turns (
            session TEXT, turn INTEGER, role TEXT, content TEXT, meta TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS traces (
            session TEXT, turn INTEGER, payload TEXT, ts REAL);
        """)
        self.db.commit()

    # -------------------------------------------------------------- state
    def load(self, session: str, case_type: str = "") -> CaseState:
        if self.use_memory:
            row = self.db.execute(
                "SELECT payload FROM case_state WHERE session=?", (session,)).fetchone()
            if row:
                return CaseState.from_dict(json.loads(row[0]))
        return CaseState(session=session, case_type=case_type)

    def save(self, state: CaseState) -> None:
        if not self.use_memory:
            return
        self.db.execute(
            "INSERT OR REPLACE INTO case_state VALUES (?,?,?)",
            (state.session, json.dumps(state.to_dict(), ensure_ascii=False), time.time()))
        self.db.commit()

    def log_fact(self, state: CaseState, fact: Fact) -> None:
        if not self.use_memory:
            return
        self.db.execute(
            "INSERT INTO fact_log VALUES (?,?,?,?,?,?,?,?,?)",
            (state.session, fact.key, json.dumps(fact.value, ensure_ascii=False),
             fact.status, fact.source, fact.turn, fact.revision,
             fact.superseded_by, time.time()))
        self.db.commit()

    def log_turn(self, session: str, turn: int, role: str, content: str, meta: dict | None = None) -> None:
        self.db.execute("INSERT INTO turns VALUES (?,?,?,?,?,?)",
                        (session, turn, role, content,
                         json.dumps(meta or {}, ensure_ascii=False), time.time()))
        self.db.commit()

    def log_trace(self, session: str, turn: int, payload: dict) -> None:
        self.db.execute("INSERT INTO traces VALUES (?,?,?,?)",
                        (session, turn, json.dumps(payload, ensure_ascii=False), time.time()))
        self.db.commit()

    def history(self, session: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT turn, role, content, meta FROM turns WHERE session=? ORDER BY rowid",
            (session,)).fetchall()
        return [{"turn": r[0], "role": r[1], "content": r[2], "meta": json.loads(r[3] or "{}")}
                for r in rows]

    # -------------------------------------------------------------- cache
    @staticmethod
    def cache_key(tool: str, args: dict, deps: list[str], state: CaseState) -> str:
        dep_values = {k: state.value(k) for k in sorted(deps)}
        raw = json.dumps([corpus_version(), tool, args, dep_values], sort_keys=True,
                         ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def cache_get(self, key: str, state: CaseState) -> dict | None:
        if not self.use_cache:
            return None
        row = self.db.execute(
            "SELECT payload, expires, deps, state_revision FROM tool_cache WHERE key=?",
            (key,)).fetchone()
        if not row:
            return None
        payload, expires, deps, rev = row
        if expires < time.time():
            self.db.execute("DELETE FROM tool_cache WHERE key=?", (key,))
            self.db.commit()
            return None
        # A cache entry is only valid if none of its fact dependencies changed.
        for dep in json.loads(deps or "[]"):
            fact = state.facts.get(dep)
            if fact is not None and fact.revision > rev:
                return None
        return json.loads(payload)

    def cache_set(self, key: str, tool: str, payload: dict, deps: list[str],
                  state: CaseState, ttl: int = 3600) -> None:
        if not self.use_cache:
            return
        self.db.execute(
            "INSERT OR REPLACE INTO tool_cache VALUES (?,?,?,?,?,?,?)",
            (key, tool, json.dumps(payload, ensure_ascii=False), json.dumps(deps),
             state.revision, time.time() + ttl, time.time()))
        self.db.commit()

    def invalidate(self, changed_keys: list[str], state: CaseState) -> int:
        """Delete cache rows that depend on any changed fact key."""
        if not changed_keys:
            return 0
        rows = self.db.execute("SELECT key, deps FROM tool_cache").fetchall()
        removed = 0
        for key, deps in rows:
            if set(json.loads(deps or "[]")) & set(changed_keys):
                self.db.execute("DELETE FROM tool_cache WHERE key=?", (key,))
                removed += 1
        self.db.commit()
        return removed

    def cache_stats(self) -> dict:
        row = self.db.execute("SELECT COUNT(*) FROM tool_cache").fetchone()
        return {"entries": row[0] if row else 0}

    def close(self) -> None:
        self.db.close()

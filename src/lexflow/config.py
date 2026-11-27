"""Shared paths and runtime configuration for LexFlow."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _load_env_files() -> None:
    """Load a local .env without adding a dependency.

    Accepts several common key names (API-key, DEEPSEEK_API_KEY, ...) and maps
    them to LLM_API_KEY. Existing environment variables win.
    """
    aliases = {"API_KEY", "APIKEY", "DEEPSEEK_API_KEY", "DEEPSEEK_KEY", "DS_API_KEY"}
    for path in (ROOT / ".env", ROOT.parent / ".env", Path.cwd() / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().replace("-", "_").upper()
            value = value.strip().strip('"').strip("'")
            if key in aliases:
                key = "LLM_API_KEY"
            os.environ.setdefault(key, value)
        break


_load_env_files()
CORPUS_DIR = DATA / "corpus"
STATUTES = CORPUS_DIR / "statutes.jsonl"
CORPUS_VERSION_FILE = CORPUS_DIR / "corpus_version.json"
ELEMENTS = DATA / "elements.json"
RUNS = ROOT / "runs"

DISCLAIMER = (
    "本系统为 NLP 课程项目演示，输出不构成正式法律意见；"
    "引用条文请以国家法律法规数据库（flk.npc.gov.cn）现行文本为准。"
)


def corpus_version() -> str:
    try:
        return json.loads(CORPUS_VERSION_FILE.read_text(encoding="utf-8"))["corpus_version"]
    except Exception:
        return "unknown"


@dataclass
class LLMConfig:
    """Configuration for the optional OpenAI-compatible model backend."""

    mode: str = field(default_factory=lambda: os.getenv("LEXFLOW_LLM", "mock"))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-chat"))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "1600")))
    timeout: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT", "60")))
    thinking: str = field(default_factory=lambda: os.getenv("LLM_THINKING", ""))

    @property
    def enabled(self) -> bool:
        return self.mode.lower() in {"api", "openai", "deepseek", "qwen"} and bool(self.api_key)


@dataclass
class Budget:
    """Per-session resource ceilings, also used to keep ablations comparable."""

    max_questions: int = 14
    max_tool_calls: int = 40
    max_llm_calls: int = 14
    max_repairs: int = 1
    cache_ttl_seconds: int = 3600

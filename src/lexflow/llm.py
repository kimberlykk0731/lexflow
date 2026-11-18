"""Optional LLM backend (OpenAI-compatible) with a deterministic fallback.

The demo must run with no API key, so every LLM call site has a rule-based
fallback.  When a key is configured, the model takes over fact extraction,
question selection and memo prose; the legal conclusions still come from the
deterministic rule layer, which keeps citations and numbers checkable.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import LLMConfig


@dataclass
class LLMResult:
    text: str
    ok: bool
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str = ""
    latency_ms: float = 0.0


class BaseLLM:
    name = "base"

    @property
    def enabled(self) -> bool:
        return False

    def complete(self, messages: list[dict], temperature: float | None = None,
                 max_tokens: int | None = None) -> LLMResult:
        return LLMResult(text="", ok=False, model=self.name, error="disabled")


class NullLLM(BaseLLM):
    """Used when no API key is present; callers exercise their fallbacks."""

    name = "mock"

    def complete(self, messages: list[dict], temperature: float | None = None,
                 max_tokens: int | None = None) -> LLMResult:
        return LLMResult(text="", ok=False, model=self.name,
                         error="mock mode: no API key configured")


class OpenAICompatLLM(BaseLLM):
    def __init__(self, cfg: LLMConfig | None = None):
        self.cfg = cfg or LLMConfig()
        self.name = self.cfg.model

    @property
    def enabled(self) -> bool:
        return self.cfg.enabled

    def complete(self, messages: list[dict], temperature: float | None = None,
                 max_tokens: int | None = None) -> LLMResult:
        if not self.enabled:
            return LLMResult(text="", ok=False, model=self.name,
                             error="no api key; set LLM_API_KEY to enable")
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.cfg.max_tokens,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error = ""
        for attempt in range(3):
            started = time.perf_counter()
            try:
                req = urllib.request.Request(
                    url, data=data,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.cfg.api_key}"})
                with urllib.request.urlopen(req, timeout=self.cfg.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                text = body["choices"][0]["message"]["content"] or ""
                usage = body.get("usage", {})
                return LLMResult(
                    text=text, ok=True, model=self.cfg.model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    latency_ms=round((time.perf_counter() - started) * 1000, 1))
            except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(1.5 * (attempt + 1))
        return LLMResult(text="", ok=False, model=self.cfg.model, error=last_error)


def build_llm(cfg: LLMConfig | None = None) -> BaseLLM:
    cfg = cfg or LLMConfig()
    if cfg.enabled:
        return OpenAICompatLLM(cfg)
    return NullLLM()


def extract_json(text: str) -> dict | None:
    """Tolerant JSON extraction from model output."""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None

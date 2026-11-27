"""Count all model call sites through one wrapper; never serialize credentials."""
from __future__ import annotations

import time
from lexflow.llm import BaseLLM


class AuditedLLM(BaseLLM):
    def __init__(self, inner: BaseLLM):
        self.inner = inner
        self.name = inner.name
        self.events: list[dict] = []

    @property
    def enabled(self):
        return self.inner.enabled

    def complete(self, messages, temperature=None, max_tokens=None):
        started = time.perf_counter()
        result = self.inner.complete(messages, temperature=temperature, max_tokens=max_tokens)
        self.events.append({"model": result.model, "ok": result.ok,
                            "error": result.error, "prompt_tokens": result.prompt_tokens,
                            "completion_tokens": result.completion_tokens,
                            "attempts": result.attempts,
                            "finish_reason": result.finish_reason,
                            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})
        return result

    def summary(self):
        return {"logical_calls": len(self.events), "successful_calls": sum(x["ok"] for x in self.events),
                "failed_calls": sum(not x["ok"] for x in self.events),
                "http_attempts": sum(x["attempts"] for x in self.events),
                "prompt_tokens": sum(x["prompt_tokens"] for x in self.events),
                "completion_tokens": sum(x["completion_tokens"] for x in self.events)}

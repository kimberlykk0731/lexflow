"""OpenAI-compatible shim that exposes LexFlow as a DLawBench lawyer model.

Run standalone:

    python external/dlawbench/server.py --port 8077

Then point DLawBench at it:

    LOCALHOST_BASE_URL=http://127.0.0.1:8077/v1 \
    LOCALHOST_API_KEY= \
    python -m dlawbench.run_dialogue --lawyer-model lexflow-full ...

Model names route to components:
    lexflow-answer-first | lexflow-gate-only | lexflow-full   lawyer policies
    lexflow-client-p-wd ...                                   deterministic client
    lexflow-rubric-judge                                      offline judge stand-in

The shim only reads the messages DLawBench sends.  It does not open the case
file, hidden facts, or the evaluation rubric; the fixed question/issue library
it uses is hand-curated and shipped with the adapter (legal_library.py).
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:  # package import
    from .agent_policy import get_agent_policy, policy_from_agent_model
    from .client_sim import ClientSimulator, persona_from_model
    from .judge import judge_reply, JUDGE_MODEL
    from .policy import LawyerPolicy, policy_from_model
except ImportError:  # script import
    from agent_policy import get_agent_policy, policy_from_agent_model
    from client_sim import ClientSimulator, persona_from_model
    from judge import judge_reply, JUDGE_MODEL
    from policy import LawyerPolicy, policy_from_model


def dispatch(model: str, messages: list[dict]) -> str:
    policy = policy_from_model(model)
    if policy:
        return LawyerPolicy(policy).respond(messages)

    agent_policy = policy_from_agent_model(model)
    if agent_policy:
        return get_agent_policy(agent_policy).respond(messages)

    if (model or "").strip().lower().startswith("lexflow-client"):
        return ClientSimulator(persona_from_model(model)).respond(messages)

    if (model or "").strip().lower() == JUDGE_MODEL:
        return judge_reply(messages)

    raise ValueError(f"unknown shim model: {model}")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LexFlowDLawBenchShim/1.0"

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") in ("/health", "/v1/health"):
            self._json(200, {"status": "ok", "models": _models()})
        elif self.path.rstrip("/") == "/v1/models":
            self._json(200, {
                "object": "list",
                "data": [{"id": name, "object": "model", "owned_by": "lexflow"} for name in _models()],
            })
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):  # noqa: N802
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._json(404, {"error": {"message": "not found"}})
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
            model = str(payload.get("model") or "")
            messages = payload.get("messages") or []
            content = dispatch(model, messages)
        except Exception as exc:  # keep the benchmark alive and fail loudly
            sys.stderr.write(f"[shim] error: {type(exc).__name__}: {exc}\n")
            self._json(500, {"error": {"message": f"{type(exc).__name__}: {exc}"}})
            return

        self._json(200, {
            "id": "chatcmpl-" + uuid.uuid4().hex[:16],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    def log_message(self, fmt, *args):  # quieter default
        if not getattr(self.server, "verbose", False):
            return
        sys.stderr.write("[shim] " + (fmt % args) + "\n")

    def _json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _models() -> list[str]:
    return [
        "lexflow-answer-first",
        "lexflow-gate-only",
        "lexflow-full",
        "lexflow-checklist-9",
        "lexflow-agent-answer-first",
        "lexflow-agent-gate-only",
        "lexflow-agent-full",
        "lexflow-client-p-wd",
        "lexflow-client-p-ws",
        "lexflow-client-p-cs",
        "lexflow-client-p-cd",
        JUDGE_MODEL,
    ]


class ShimServer:
    """In-process server helper used by run.py."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, verbose: bool = False):
        self.httpd = ThreadingHTTPServer((host, port), Handler)
        self.httpd.daemon_threads = True
        self.httpd.verbose = verbose
        self.host, self.port = self.httpd.server_address[:2]
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="dlawbench-shim")
        self.thread.daemon = True

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    def start(self) -> "ShimServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="LexFlow DLawBench shim server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8077)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    server = ShimServer(args.host, args.port, verbose=args.verbose)
    print(f"LexFlow DLawBench shim listening on {server.base_url}", flush=True)
    try:
        server.httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.httpd.server_close()


if __name__ == "__main__":
    main()

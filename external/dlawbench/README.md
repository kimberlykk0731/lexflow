# DLawBench adapter

Adapted external evaluation of LexFlow on
[DLawBench](https://github.com/SKYLENAGE-AI/DLawBench).  **Not an official
leaderboard entry.**

- `server.py` — OpenAI-compatible shim (`/v1/chat/completions`) routing
  `lexflow-answer-first`, `lexflow-gate-only`, `lexflow-full`,
  `lexflow-client-p-*` and `lexflow-rubric-judge`.
- `policy.py` — LexFlow's gate → ask → memo control flow in DLawBench's
  `talk_to_client` / `write_memo` protocol.
- `client_sim.py` — deterministic persona client (reads only `client_belief`
  from the official client prompt).
- `judge.py` — deterministic lexical judge answering the official judge
  prompts; formulas/denominators stay official.
- `run.py` — one command: 3 policies × N CN × P_WD → official evaluation →
  cluster-bootstrap CI → `runs/external/`.
- `verify.py` — acceptance checks (n, 7 metrics, CIs, hashes, provenance,
  no-rubric-access).
- `upstream/` — pinned DLawBench subset; see `upstream/VENDORED.json`.

Method and caveats: [`docs/EXTERNAL_EVAL.md`](../../docs/EXTERNAL_EVAL.md).

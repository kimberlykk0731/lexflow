"""Run the adapted LexFlow × DLawBench matrix end-to-end.

One command does everything:

    python external/dlawbench/run.py --n-cases 10

    # D2 extension: all 30 Chinese cases, 90 sessions
    python external/dlawbench/run.py --n-cases 30

It starts the local shim, runs the three ablation policies against the vendored
DLawBench dialogue environment with the P_WD persona, evaluates every session
through the *official* ``dlawbench.evaluate.evaluate_session`` code path, then
writes ``scores.csv``, ``summary.md``, ``leaderboard.md`` and
``run_manifest.json`` under ``runs/external/``.

The judge is a deterministic lexical stand-in (see judge.py); this is an
adapted run, not an official leaderboard entry.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
UPSTREAM = HERE / "upstream"
RUNS_DIR = ROOT / "runs" / "external"
CASE_FILE = UPSTREAM / "data" / "case_backgrounds" / "cases_cn.jsonl"

sys.path.insert(0, str(UPSTREAM / "src"))
sys.path.insert(0, str(UPSTREAM / "scripts"))
sys.path.insert(0, str(HERE))

try:
    from .bootstrap import cluster_bootstrap
    from .client_sim import client_model, PERSONAS
    from .judge import JUDGE_MODEL
    from .policy import POLICIES, model_name as policy_model
    from .server import ShimServer
except ImportError:  # script execution
    from bootstrap import cluster_bootstrap
    from client_sim import client_model, PERSONAS
    from judge import JUDGE_MODEL
    from policy import POLICIES, model_name as policy_model
    from server import ShimServer


# ── DLawBench imports (vendored, unmodified) ────────────────────────────────
def _import_dlawbench():
    os.environ.setdefault("LOCALHOST_API_KEY", "")
    from dlawbench import api_utils
    from dlawbench.agent_environment import AgentEnvironment
    from dlawbench.case_utils import load_case, make_jsonl_ref, normalize_case
    from dlawbench.client_npc import load_persona
    from dlawbench.evaluate import evaluate_session
    import metrics  # vendored scripts/metrics.py

    return {
        "api_utils": api_utils,
        "AgentEnvironment": AgentEnvironment,
        "load_case": load_case,
        "make_jsonl_ref": make_jsonl_ref,
        "normalize_case": normalize_case,
        "load_persona": load_persona,
        "evaluate_session": evaluate_session,
        "metrics": metrics,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return ""


def _read_cases(limit: int, wanted: list[str]) -> list[dict]:
    records = []
    with CASE_FILE.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            records.append((line_no, json.loads(line)))
    if wanted:
        wanted_set = set(wanted)
        records = [r for r in records if r[1].get("id") in wanted_set]
    return [{"line": line_no, "raw": raw} for line_no, raw in records[:limit]]


def _session_path(out_dir: Path, policy: str, case_id: str, persona: str) -> Path:
    return out_dir / policy / f"session_{case_id}_{persona}_{policy}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-cases", type=int, default=10,
                        help="Number of Chinese cases (default 10 for the D1 matrix)")
    parser.add_argument("--case-ids", default="",
                        help="Comma-separated case ids (overrides the first-N selection)")
    parser.add_argument("--personas", default="P_WD",
                        help="Comma-separated persona keys (default P_WD)")
    parser.add_argument("--policies", default=",".join(POLICIES),
                        help="Comma-separated policies (default all three)")
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20261124)
    parser.add_argument("--output-dir", default=str(RUNS_DIR))
    parser.add_argument("--resume", action="store_true",
                        help="Reuse finished dialogue sessions in output-dir")
    parser.add_argument("--skip-eval", action="store_true",
                        help="Only run dialogues (debug)")
    args = parser.parse_args()

    policies = [p.strip() for p in args.policies.split(",") if p.strip()]
    for policy in policies:
        if policy not in POLICIES:
            raise SystemExit(f"unknown policy: {policy} (choose from {POLICIES})")
    personas = [p.strip() for p in args.personas.split(",") if p.strip()]
    for persona in personas:
        if persona not in PERSONAS:
            raise SystemExit(f"unknown persona: {persona}")

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = _read_cases(args.n_cases, [c for c in args.case_ids.split(",") if c])
    if not cases:
        raise SystemExit("no cases selected")

    started = time.time()
    server = ShimServer(verbose=False).start()
    os.environ["LOCALHOST_BASE_URL"] = server.base_url

    dl = _import_dlawbench()
    api_utils = dl["api_utils"]
    local_names = [policy_model(p) for p in policies]
    local_names += [client_model(p) for p in personas]
    local_names += [JUDGE_MODEL]
    api_utils.LOCALHOST_MODELS[:] = list(dict.fromkeys(local_names + api_utils.LOCALHOST_MODELS))

    print(f"[shim] {server.base_url}")
    print(f"[cases] {len(cases)} CN × {len(personas)} persona × {len(policies)} policies "
          f"= {len(cases) * len(personas) * len(policies)} sessions")

    sessions: list[tuple[str, str, dict, Path]] = []
    failures = 0
    try:
        for persona in personas:
            persona_obj = dl["load_persona"](persona)
            for policy in policies:
                lawyer_model = policy_model(policy)
                for item in cases:
                    raw = item["raw"]
                    case = dl["normalize_case"](raw)
                    case_id = case.get("case_id")
                    path = _session_path(out_dir, policy, case_id, persona)

                    if args.resume and path.is_file():
                        try:
                            with path.open("r", encoding="utf-8") as handle:
                                session = json.load(handle)
                            if session.get("status") in ("memo_submitted", "max_turns_reached"):
                                sessions.append((policy, persona, session, path))
                                print(f"[resume] {policy:12s} {case_id} {persona}")
                                continue
                        except (OSError, json.JSONDecodeError):
                            pass

                    env = dl["AgentEnvironment"](
                        case=case,
                        persona=persona_obj,
                        lawyer_model=lawyer_model,
                        client_model=client_model(persona),
                        max_turns=args.max_turns,
                        client_kwargs={"retries": 1, "timeout": 60},
                        lawyer_kwargs={"retries": 1, "timeout": 60},
                    )
                    session = env.run()
                    session["case_file"] = CASE_FILE.name
                    session["case_line"] = item["line"]
                    session["jurisdiction"] = case.get("jurisdiction")
                    session["policy"] = policy
                    session["persona_key"] = persona

                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("w", encoding="utf-8") as handle:
                        json.dump(session, handle, ensure_ascii=False, indent=2)

                    sessions.append((policy, persona, session, path))
                    marker = "ok" if session.get("status") == "memo_submitted" else session.get("status")
                    print(f"[dialogue] {policy:12s} {case_id} {persona} "
                          f"turns={session.get('turns_used')} {marker}")

        if args.skip_eval:
            print("[eval] skipped")
            return 0

        # Evaluate in place through the official evaluator.
        for index, (policy, persona, session, path) in enumerate(sessions, start=1):
            try:
                case = dl["load_case"](
                    dl["make_jsonl_ref"](str(CASE_FILE), session.get("case_line"),
                                         session.get("case_id"))
                )
                evaluation = dl["evaluate_session"](session, case, JUDGE_MODEL)
                session["evaluation"] = evaluation
                with path.open("w", encoding="utf-8") as handle:
                    json.dump(session, handle, ensure_ascii=False, indent=2)
                scores = evaluation.get("scores", {})
                print(f"[eval {index:>3}/{len(sessions)}] {policy:12s} "
                      f"{session.get('case_id')} FFS={scores.get('FFS')} "
                      f"MES={scores.get('MES')} disc={scores.get('discovery_rate')} "
                      f"abs={scores.get('absolute_accuracy')} ground={scores.get('grounding_rate')}")
            except Exception as exc:
                failures += 1
                print(f"[eval-error] {path.name}: {type(exc).__name__}: {exc}")
    finally:
        server.stop()

    rows_by_policy: dict[str, list[dict]] = {}
    status_counts: dict[str, int] = {}
    raw_scores: dict[str, dict] = {}
    for policy, persona, session, path in sessions:
        status = session.get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        evaluation = session.get("evaluation")
        if not isinstance(evaluation, dict) or not isinstance(evaluation.get("scores"), dict):
            failures += 1
            continue
        row = dl["metrics"].session_metrics(path, session, session.get("jurisdiction") or "CN")
        row["case_id"] = session.get("case_id")
        row["policy"] = policy
        row["persona"] = persona
        rows_by_policy.setdefault(policy, []).append(row)
        raw_scores[str(path)] = evaluation.get("scores", {})

    metric_keys = list(dl["metrics"].METRIC_KEYS)
    ci = cluster_bootstrap(rows_by_policy, metric_keys,
                           n_boot=args.bootstrap, seed=args.seed)

    elapsed = time.time() - started
    _write_outputs(out_dir, args, policies, personas, cases, sessions,
                   rows_by_policy, ci, raw_scores, status_counts, failures, elapsed, dl)

    print(f"\n[done] {sum(len(v) for v in rows_by_policy.values())} evaluated sessions "
          f"in {elapsed:.1f}s")
    print(f"[out] {out_dir / 'summary.md'}")
    print(f"[out] {out_dir / 'scores.csv'}")
    print(f"[out] {out_dir / 'run_manifest.json'}")
    return 0 if failures == 0 else 1


def _write_outputs(out_dir, args, policies, personas, cases, sessions,
                   rows_by_policy, ci, raw_scores, status_counts, failures,
                   elapsed, dl) -> None:
    metrics = dl["metrics"]
    metric_keys = list(metrics.METRIC_KEYS)
    display = metrics.DISPLAY_NAMES

    # scores.csv ------------------------------------------------------------
    csv_path = out_dir / "scores.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["policy", "case_id", "persona", "session_file", "turns", "status"]
        fieldnames += metric_keys
        fieldnames += ["FFS", "MES", "EAS", "discovery_rate", "accuracy_rate",
                       "absolute_accuracy", "grounding_rate", "n_facts", "n_covered",
                       "n_claims_total", "n_claims_ungrounded"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for policy, persona, session, path in sessions:
            evaluation = session.get("evaluation") or {}
            scores = evaluation.get("scores") or {}
            row = metrics.session_metrics(path, session, session.get("jurisdiction") or "CN") \
                if scores else {}
            record = {
                "policy": policy,
                "case_id": session.get("case_id"),
                "persona": persona,
                "session_file": path.name,
                "turns": session.get("turns_used"),
                "status": session.get("status"),
            }
            for key in metric_keys:
                record[key] = row.get(key)
            for key in ("FFS", "MES", "EAS", "discovery_rate", "accuracy_rate",
                        "absolute_accuracy", "grounding_rate", "n_facts", "n_covered",
                        "n_claims_total", "n_claims_ungrounded"):
                record[key] = scores.get(key)
            writer.writerow(record)

    # summary.md ------------------------------------------------------------
    def cell(policy: str, key: str) -> str:
        mean, lo, hi = ci.get(policy, {}).get(key, (0.0, 0.0, 0.0))
        return f"{mean:.3f} [{lo:.3f}, {hi:.3f}]"

    n_by_policy = {policy: len(rows_by_policy.get(policy, [])) for policy in policies}
    n = max(n_by_policy.values()) if n_by_policy else 0
    upstream = json.loads((UPSTREAM / "VENDORED.json").read_text(encoding="utf-8"))
    lexflow_commit = _git("rev-parse", "HEAD") or "unknown"
    dirty = bool(_git("status", "--porcelain"))
    generated = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    lines = [
        "# LexFlow × DLawBench — adapted external evaluation",
        "",
        "> **Adapted run, not an official leaderboard entry.**  The lawyer is the LexFlow",
        "> policy shim; the client and judge are deterministic offline stand-ins. Official",
        "> DLawBench rubric text, metric formulas and denominators are used unchanged, but",
        "> absolute scores are not comparable to the DLawBench leaderboard.",
        "",
        f"- Generated: `{generated}`",
        f"- DLawBench: `{upstream['repo']}` @ `{upstream['commit']}` "
        f"(MIT code / CC BY 4.0 data)",
        f"- LexFlow: `{lexflow_commit}`" + (" (dirty working tree)" if dirty else ""),
        f"- Cases: {len(cases)} Chinese-law cases from `cases_cn.jsonl` "
        f"({', '.join(c['raw']['id'] for c in cases[:3])}{'…' if len(cases) > 3 else ''})",
        f"- Persona(s): {', '.join(personas)} · max turns: {args.max_turns}",
        f"- Sessions: {sum(n_by_policy.values())} "
        f"({len(policies)} policies × {n} cases)",
        f"- Status: {', '.join(f'{k}={v}' for k, v in sorted(status_counts.items()))}"
        + (f", eval_failures={failures}" if failures else ""),
        f"- Judge: `{JUDGE_MODEL}` — deterministic lexical rubric matcher, "
        "stand-in for the official LLM judge",
        f"- CI: {args.bootstrap} cluster-bootstrap resamples by case, 95% percentile, seed {args.seed}",
        "",
        "## 3 × 7 table",
        "",
        "| Policy | n | Fact Coverage | Inquiry | Elicitation | Fact Resolution | "
        "Issue Resolution | Resolution | Fidelity |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in policies:
        lines.append(
            f"| {policy} | {n_by_policy.get(policy, 0)} | "
            + " | ".join(cell(policy, key) for key in metric_keys)
            + " |"
        )
    lines += [
        "",
        "Each cell is `mean [95% CI]`. The CI resamples cases (clusters), not sessions,",
        "so the three policies are evaluated on the same resampled case set.",
        "",
        "## Official definitions (unchanged)",
        "",
        "| Metric | Official input | Formula |",
        "|---|---|---|",
        "| Fact Coverage | `discovery_rate` | covered facts / all case facts |",
        "| Inquiry | `EAS` | mean expected-action rubric score (0/1) |",
        "| Elicitation | derived | (Fact Coverage + Inquiry) / 2 |",
        "| Fact Resolution | `absolute_accuracy` | correct facts / all case facts |",
        "| Issue Resolution | `MES` | mean memo-expectation rubric score (0/1) |",
        "| Resolution | derived | (Fact Resolution + Issue Resolution) / 2 |",
        "| Fidelity | `grounding_rate` | grounded claims / total claims |",
        "",
        "Source: `external/dlawbench/upstream/scripts/metrics.py` and",
        "`external/dlawbench/upstream/src/dlawbench/evaluate.py` at the pinned commit.",
        "`FFS` (required sections) is a format filter, not a ranking metric.",
        "",
        "## How to read this",
        "",
        "- `answer_first` never asks a question: memo from the opening message only.",
        "- `gate_only` runs LexFlow's sufficiency gate, asks the domain intake checklist,",
        "  then writes the memo without provenance/verification sections.",
        "- `full` adds per-fact provenance and an explicit verification section, and",
        "  marks unresolved information gaps.",
        "- The shim only sees the DLawBench messages. It never opens the case file,",
        "  the hidden facts, or `evaluation_criteria`.",
        "- The deterministic client reveals a `client_belief` only when the lawyer asks",
        "  about the same topic; it is not the official LLM client.",
        "- Because the judge is lexical, treat **within-run policy deltas** as the signal",
        "  and absolute values as pipeline diagnostics only.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"python external/dlawbench/run.py --n-cases {len(cases)} --personas {','.join(personas)}",
        "```",
        "",
        "## Files",
        "",
        "- `runs/external/<policy>/session_*.json` — full dialogue + evaluation",
        "- `runs/external/scores.csv` — one row per session",
        "- `runs/external/run_manifest.json` — commits, licenses, n, hashes, command",
        "- `runs/external/leaderboard.md` — optional mini leaderboard by Elicitation",
        "- `docs/EXTERNAL_EVAL.md` — one-page method and caveats",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # leaderboard.md --------------------------------------------------------
    ranked = sorted(
        policies,
        key=lambda p: ci.get(p, {}).get("elicitation", (0.0, 0.0, 0.0))[0],
        reverse=True,
    )
    lb = [
        "# Mini leaderboard — adapted run",
        "",
        "Ranked by Elicitation. **Not** an official DLawBench leaderboard; n is cases per policy.",
        "",
        "| Rank | Policy | n | Elicitation | Resolution | Fidelity |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for rank, policy in enumerate(ranked, start=1):
        lb.append(
            f"| {rank} | {policy} | {n_by_policy.get(policy, 0)} | "
            f"{cell(policy, 'elicitation')} | {cell(policy, 'resolution')} | "
            f"{cell(policy, 'fidelity')} |"
        )
    (out_dir / "leaderboard.md").write_text("\n".join(lb) + "\n", encoding="utf-8")

    # run_manifest.json -----------------------------------------------------
    manifest = {
        "generated_at": generated,
        "command": " ".join([sys.executable, *sys.argv]),
        "argv": sys.argv,
        "elapsed_seconds": round(elapsed, 1),
        "n_cases": len(cases),
        "case_ids": [c["raw"]["id"] for c in cases],
        "personas": personas,
        "policies": policies,
        "max_turns": args.max_turns,
        "sessions_expected": len(cases) * len(personas) * len(policies),
        "sessions_evaluated": sum(len(v) for v in rows_by_policy.values()),
        "status_counts": status_counts,
        "eval_failures": failures,
        "bootstrap": {"resamples": args.bootstrap, "seed": args.seed, "cluster": "case_id",
                      "confidence": 0.95},
        "judge": {
            "model": JUDGE_MODEL,
            "kind": "deterministic lexical rubric matcher",
            "official_prompt": True,
            "official_formulas": True,
        },
        "dlawbench": {
            "repo": upstream["repo"],
            "commit": upstream["commit"],
            "license": upstream["license"],
            "case_file": CASE_FILE.name,
            "case_file_sha256": _sha256(CASE_FILE),
            "vendored_files": len(upstream["files"]),
        },
        "lexflow": {
            "commit": lexflow_commit,
            "dirty": dirty,
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
        "metrics": metric_keys,
        "ci": {
            policy: {key: {"mean": v[0], "lo": v[1], "hi": v[2]}
                     for key, v in per_metric.items()}
            for policy, per_metric in ci.items()
        },
        "files": ["summary.md", "scores.csv", "leaderboard.md", "run_manifest.json"],
    }
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())

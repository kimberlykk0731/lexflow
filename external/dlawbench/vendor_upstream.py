"""Vendor the pinned DLawBench subset used by the external evaluation.

Run from the lexflow repository root:

    python external/dlawbench/vendor_upstream.py --source ../dlawbench_upstream

The upstream commit is recorded in VENDORED.json and every copied file is
hashed so that ``run.py --check`` can prove the rubric / scorer were not edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEST = HERE / "upstream"

FILES = [
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "src/dlawbench/__init__.py",
    "src/dlawbench/api_utils.py",
    "src/dlawbench/agent_environment.py",
    "src/dlawbench/case_utils.py",
    "src/dlawbench/client_npc.py",
    "src/dlawbench/evaluate.py",
    "src/dlawbench/panel_evaluate.py",
    "src/dlawbench/paths.py",
    "src/dlawbench/run_dialogue.py",
    "src/dlawbench/run_evaluation.py",
    "config/lawyer_agent_prompt.txt",
    "config/lawyer_agent_prompt_en.txt",
    "config/client_npc_prompt.txt",
    "config/client_npc_prompt_en.txt",
    "config/personas.json",
    "config/models.json",
    "config/benchmark_models.json",
    "data/LICENSE",
    "data/case_backgrounds/cases_cn.jsonl",
    "metadata/case_index.jsonl",
    "metadata/manifest.csv",
    "metadata/dataset_summary.json",
    "schema/case.schema.json",
    "scripts/metrics.py",
]


def sha256(path: Path) -> str:
    """Hash with line endings normalised so Windows/macOS/Linux agree."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk.replace(b"\r\n", b"\n"))
    return h.hexdigest()


def git_commit(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Path to a DLawBench checkout")
    ap.add_argument("--repo", default="https://github.com/SKYLENAGE-AI/DLawBench")
    args = ap.parse_args()

    src = Path(args.source).resolve()
    if not (src / "src/dlawbench/evaluate.py").is_file():
        raise SystemExit(f"not a DLawBench checkout: {src}")

    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    copied = {}
    for rel in FILES:
        source_file = src / rel
        if not source_file.is_file():
            raise SystemExit(f"missing upstream file: {rel}")
        target = DEST / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
        copied[rel] = sha256(target)

    meta = {
        "repo": args.repo,
        "commit": git_commit(src),
        "vendored_at": datetime.now(timezone.utc).isoformat(),
        "license": {
            "code": "MIT (upstream LICENSE)",
            "data": "CC BY 4.0 (upstream data/LICENSE)",
        },
        "files": copied,
        "note": (
            "Only the CN case file, runner/scorer code, prompts, personas and "
            "public metadata are vendored. Upstream rubric text and metric "
            "denominators are byte-identical to the pinned commit."
        ),
    }
    (DEST / "VENDORED.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"vendored {len(copied)} files -> {DEST}")
    print(f"commit {meta['commit']}")


if __name__ == "__main__":
    main()

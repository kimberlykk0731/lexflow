"""Acceptance checks for the adapted DLawBench run.

    python external/dlawbench/verify.py

Verifies the hand-off acceptance list: one command produced >= 30 sessions,
all seven metrics are present with 95% CIs, the shim never reads rubric/case
data, the vendored DLawBench scorer is byte-identical to the pinned commit,
and the commit / license / n are recorded.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
UPSTREAM = HERE / "upstream"
DEFAULT_RUN = ROOT / "runs" / "external"

METRICS = ["fact_coverage", "inquiry", "elicitation", "fact_resolution",
           "issue_resolution", "resolution", "fidelity"]
FORBIDDEN = ["evaluation_criteria", "expected_inquiries", "memo_expectations",
             "court_record", "actual_situation", "cases_cn", "case_backgrounds"]

# Distinctive strings from entries that were removed because they carried
# case-specific content.  Kept as a regression guard: re-introducing them
# means the issue library is being fitted to the benchmark again.
LIBRARY_FORBIDDEN = ("C市规划区", "隐蔽工程", "承租人明知现状", "违法占地的确认",
                     "水管电线的收据")
ENTITY_PATTERNS = (
    re.compile(r"[A-Z]市"),
    re.compile(r"[A-Z]公司"),
    re.compile(r"某[\u4e00-\u9fff]{1,2}"),
    re.compile(r"\d+(?:\.\d+)?万"),
    re.compile(r"\d[\d,]{2,}\.?\d*元"),
)
ENTITY_ALLOW = {"某公司", "某公司。", "某区"}


def sha256(path: Path) -> str:
    """Hash with line endings normalised (matches vendor_upstream.py)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk.replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def check(condition: bool, label: str, detail: str = "") -> bool:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return condition


def library_leakage() -> list[str]:
    """Case-specific strings that leaked into the hand-written issue library.

    The shim never opens the case file at run time, but the question/issue
    library is written by humans, so case-specific entities (``C市``), amounts
    and dates can be copied into it.  The 2026-11 review found and removed
    exactly this; this check keeps it from coming back.
    """
    library = (HERE / "legal_library.py").read_text(encoding="utf-8")
    problems = [f"blacklisted phrase: {phrase}" for phrase in LIBRARY_FORBIDDEN
                if phrase in library]

    case_file = UPSTREAM / "data" / "case_backgrounds" / "cases_cn.jsonl"
    tokens: set[str] = set()
    for line in case_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        criteria = case.get("evaluation_criteria") or {}
        text = " ".join(
            [case["opening"]]
            + [f["client_belief"] + " " + f["court_record"] for f in case["facts"]]
            + criteria.get("memo_expectations", [])
            + criteria.get("expected_inquiries", [])
        )
        for pattern in ENTITY_PATTERNS:
            tokens.update(m.group(0) for m in pattern.finditer(text))
    for token in sorted(tokens - ENTITY_ALLOW):
        if len(token) >= 3 and token in library:
            problems.append(f"case entity: {token!r}")
    return problems


def main() -> int:
    run_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_RUN
    ok = True

    manifest_path = run_dir / "run_manifest.json"
    summary_path = run_dir / "summary.md"
    csv_path = run_dir / "scores.csv"
    ok &= check(manifest_path.is_file(), "run_manifest.json exists")
    ok &= check(summary_path.is_file(), "summary.md exists")
    ok &= check(csv_path.is_file(), "scores.csv exists")
    if not (manifest_path.is_file() and summary_path.is_file() and csv_path.is_file()):
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = summary_path.read_text(encoding="utf-8")

    # 1. n sessions -------------------------------------------------------
    session_files = sorted(run_dir.glob("*/session_*.json"))
    expected = int(manifest.get("sessions_expected") or 0)
    if expected:
        ok &= check(len(session_files) == expected, "session files match the manifest",
                    f"n={len(session_files)} expected={expected}")
    else:
        ok &= check(len(session_files) >= 30, "at least 30 session files",
                    f"n={len(session_files)}")
    evaluated = 0
    for path in session_files:
        session = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(session.get("evaluation", {}).get("scores"), dict):
            evaluated += 1
    ok &= check(evaluated == len(session_files),
                "every session has evaluation scores", f"{evaluated}/{len(session_files)}")

    # 2. seven metrics + CI ----------------------------------------------
    ci = manifest.get("ci", {})
    ok &= check(all(key in ci.get(p, {}) for p in ci for key in METRICS),
                "manifest records all 7 metrics per policy")
    table_rows = [line for line in summary.splitlines()
                  if line.startswith("| ") and "[" in line]
    cells = re.findall(r"\d+\.\d+\s*\[\d+\.\d+,\s*\d+\.\d+\]", "\n".join(table_rows))
    ok &= check(len(table_rows) >= 3 and len(cells) >= 21,
                "summary table has mean [95% CI] cells", f"rows={len(table_rows)} cells={len(cells)}")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    ok &= check(all(metric in header for metric in METRICS),
                "scores.csv has all 7 metric columns")

    # 3. provenance -------------------------------------------------------
    dlb = manifest.get("dlawbench", {})
    ok &= check(bool(re.fullmatch(r"[0-9a-f]{40}", str(dlb.get("commit", "")))),
                "DLawBench commit recorded", str(dlb.get("commit", ""))[:12])
    ok &= check(bool(dlb.get("license")), "DLawBench license recorded")
    ok &= check(bool(manifest.get("lexflow", {}).get("commit")), "LexFlow commit recorded")
    case_ids = manifest.get("case_ids") or []
    ok &= check(int(manifest.get("n_cases", 0)) >= 1
                and int(manifest.get("n_cases", 0)) == len(case_ids),
                "n cases recorded and matches case_ids",
                f"n_cases={manifest.get('n_cases')} ids={len(case_ids)}")

    # 4. vendored scorer untouched ---------------------------------------
    vendored = json.loads((UPSTREAM / "VENDORED.json").read_text(encoding="utf-8"))
    mismatched = []
    for rel, expected in vendored["files"].items():
        path = UPSTREAM / rel
        if not path.is_file() or sha256(path) != expected:
            mismatched.append(rel)
    ok &= check(not mismatched, "vendored DLawBench files match pinned hashes",
                f"{len(vendored['files'])} files" if not mismatched else str(mismatched[:3]))
    for rel in ("src/dlawbench/evaluate.py", "scripts/metrics.py"):
        ok &= check(rel in vendored["files"], f"official scorer vendored: {rel}")

    # 5. shim does not read rubric / case data ---------------------------
    forbidden_hits = []
    for name in ("server.py", "policy.py", "agent_policy.py", "client_sim.py",
                 "legal_library.py", "textutil.py"):
        text = (HERE / name).read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text:
                forbidden_hits.append(f"{name}:{token}")
    ok &= check(not forbidden_hits, "shim/client/policy never reference rubric or case data",
                str(forbidden_hits))
    leaks = library_leakage()
    ok &= check(not leaks, "issue library carries no case-specific entities/phrases",
                str(leaks[:5]))

    # 6. caveat is visible ------------------------------------------------
    ok &= check("Adapted run, not an official leaderboard entry" in summary,
                "summary states it is an adapted run, not an official leaderboard")
    judge = manifest.get("judge", {})
    judge_kind = str(judge.get("kind", ""))
    if "deterministic" in judge_kind.lower():
        ok &= check("deterministic" in summary.lower(), "summary discloses the deterministic judge")
    else:
        ok &= check(str(judge.get("model", "")) in summary,
                    "summary names the external judge model")

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

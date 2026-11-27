"""Post-hoc diagnostics for the DLawBench adapter.

Outputs:
  runs/external/domain_breakdown.csv / .md
  runs/external/paired_deltas.csv / .md

The domain analysis uses the 30 ``full`` P_WD sessions and the benchmark's own
missed-fact list.  The paired deltas use case-level bootstrap on the existing
scores, so no dialogue is re-run.
"""
from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))

from legal_library import DOMAINS, detect_domain, domain_label  # noqa: E402

RUNS = ROOT / "runs" / "external"
CASES = HERE / "upstream" / "data" / "case_backgrounds" / "cases_cn.jsonl"

METRICS = ["fact_coverage", "inquiry", "elicitation", "fact_resolution",
           "issue_resolution", "resolution", "fidelity"]
SHORT = {
    "fact_coverage": "Fact Coverage",
    "inquiry": "Inquiry",
    "elicitation": "Elicitation",
    "resolution": "Resolution",
}


def load_cases() -> dict[str, dict]:
    cases = {}
    for line in CASES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        cases[case["id"]] = case
    return cases


def load_sessions(policy: str) -> list[dict]:
    out = []
    for path in sorted((RUNS / policy).glob("session_*.json")):
        with path.open(encoding="utf-8") as handle:
            out.append(json.load(handle))
    return out


def domain_table(cases: dict[str, dict]) -> list[dict]:
    rows: dict[str, dict] = {}
    for session in load_sessions("full"):
        case = cases[session["case_id"]]
        text = case["opening"] + " " + " ".join(f["client_belief"] for f in case["facts"])
        domain = detect_domain(text)
        entry = rows.setdefault(domain, {
            "domain": domain, "label": domain_label(domain), "n": 0,
            "coverage": [], "inquiry": [], "missed": Counter(),
        })
        scores = session["evaluation"]["scores"]
        entry["n"] += 1
        entry["coverage"].append(scores["discovery_rate"])
        entry["inquiry"].append(scores["EAS"])
        missed_ids = session["evaluation"]["fact_evaluation"]["discovery"]["missed"]
        fact_map = {f["fact_id"]: f for f in case["facts"]}
        for fid in missed_ids:
            fact = fact_map.get(fid)
            if not fact:
                continue
            entry["missed"][fact["client_belief"][:46]] += 1
    out = []
    for entry in rows.values():
        top = entry["missed"].most_common(2)
        out.append({
            "domain": entry["domain"],
            "label": entry["label"],
            "n": entry["n"],
            "coverage": statistics.fmean(entry["coverage"]),
            "inquiry": statistics.fmean(entry["inquiry"]),
            "missed": sum(entry["missed"].values()),
            "examples": " / ".join(f"{text}（{count}）" for text, count in top),
        })
    return sorted(out, key=lambda row: (-row["n"], row["domain"]))


def load_scores() -> dict[str, dict[str, dict]]:
    """policy -> case_id -> metric row."""
    result: dict[str, dict[str, dict]] = defaultdict(dict)
    sources = [
        ("answer_first", RUNS / "scores.csv"),
        ("gate_only", RUNS / "scores.csv"),
        ("full", RUNS / "scores.csv"),
        ("checklist_9", RUNS / "checklist9" / "scores.csv"),
    ]
    for policy, path in sources:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["policy"] != policy:
                    continue
                result[policy][row["case_id"]] = {
                    key: float(row[key]) for key in METRICS if row.get(key) not in (None, "")
                }
    return result


def paired_delta(scores, left: str, right: str, metric: str,
                 n_boot: int = 5000, seed: int = 20261124):
    cases = sorted(set(scores[left]) & set(scores[right]))
    diffs = []
    for case in cases:
        if metric in scores[left][case] and metric in scores[right][case]:
            diffs.append(scores[left][case][metric] - scores[right][case][metric])
    if not diffs:
        return None
    rng = random.Random(seed)
    draws = []
    for _ in range(n_boot):
        sample = [rng.choice(diffs) for _ in diffs]
        draws.append(statistics.fmean(sample))
    draws.sort()
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    return statistics.fmean(diffs), lo, hi, len(diffs)


def main() -> None:
    cases = load_cases()
    domains = domain_table(cases)
    with (RUNS / "domain_breakdown.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(domains[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(domains)
    lines = [
        "# Per-domain coverage (full policy, P_WD, n=30)",
        "",
        "| Domain | n | Coverage | Inquiry | Missed facts | Most frequent missed facts |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in domains:
        lines.append(
            f"| {row['label']} | {row['n']} | {row['coverage']:.3f} | "
            f"{row['inquiry']:.3f} | {row['missed']} | {row['examples']} |"
        )
    (RUNS / "domain_breakdown.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    scores = load_scores()
    pairs = [
        ("gate_only", "answer_first"),
        ("full", "gate_only"),
        ("checklist_9", "gate_only"),
        ("full", "checklist_9"),
    ]
    delta_rows = []
    for left, right in pairs:
        for metric in ("fact_coverage", "inquiry", "elicitation", "resolution"):
            got = paired_delta(scores, left, right, metric)
            if got:
                mean, lo, hi, n = got
                delta_rows.append({
                    "comparison": f"{left} - {right}",
                    "metric": metric,
                    "mean": round(mean, 4),
                    "lo": round(lo, 4),
                    "hi": round(hi, 4),
                    "n_cases": n,
                })
    with (RUNS / "paired_deltas.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["comparison", "metric", "mean", "lo", "hi", "n_cases"],
                               lineterminator="\n")
        writer.writeheader()
        writer.writerows(delta_rows)
    lines = [
        "# Paired case-level deltas (95% CI)",
        "",
        "| Comparison | Metric | Delta [95% CI] | n cases |",
        "|---|---|---:|---:|",
    ]
    for row in delta_rows:
        lines.append(
            f"| {row['comparison']} | {SHORT.get(row['metric'], row['metric'])} | "
            f"{row['mean']:+.4f} [{row['lo']:+.4f}, {row['hi']:+.4f}] | {row['n_cases']} |"
        )
    (RUNS / "paired_deltas.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", RUNS / "domain_breakdown.md")
    print("wrote", RUNS / "paired_deltas.md")


if __name__ == "__main__":
    main()

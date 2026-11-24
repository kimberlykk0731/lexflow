"""Cluster bootstrap confidence intervals (pure stdlib).

Sessions are clustered by case: a case resampled once brings all of its
sessions (one per policy and persona) with it.  This preserves the pairing
between policies that see the same cases.
"""
from __future__ import annotations

import random
import statistics


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * q))
    return ordered[max(0, min(index, len(ordered) - 1))]


def cluster_bootstrap(
    rows_by_policy: dict[str, list[dict]],
    metric_keys: list[str],
    n_boot: int = 5000,
    seed: int = 20261124,
    confidence: float = 0.95,
) -> dict[str, dict[str, tuple[float, float, float]]]:
    """Return policy -> metric -> (mean, lo, hi).

    ``rows_by_policy`` maps a policy label to session metric rows, each of which
    must carry ``case_id`` and the metric keys.
    """
    by_policy_case: dict[str, dict[str, list[dict]]] = {}
    clusters: set[str] = set()
    for policy, rows in rows_by_policy.items():
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            case_id = str(row["case_id"])
            grouped.setdefault(case_id, []).append(row)
            clusters.add(case_id)
        by_policy_case[policy] = grouped

    cluster_list = sorted(clusters)
    if not cluster_list:
        return {}

    rng = random.Random(seed)
    draws: dict[str, dict[str, list[float]]] = {
        policy: {key: [] for key in metric_keys} for policy in rows_by_policy
    }

    for _ in range(max(200, int(n_boot))):
        sample = [rng.choice(cluster_list) for _ in cluster_list]
        for policy, grouped in by_policy_case.items():
            rows: list[dict] = []
            for case_id in sample:
                rows.extend(grouped.get(case_id, []))
            for key in metric_keys:
                draws[policy][key].append(
                    statistics.fmean(float(row[key]) for row in rows) if rows else 0.0
                )

    alpha = (1.0 - confidence) / 2.0
    out: dict[str, dict[str, tuple[float, float, float]]] = {}
    for policy, rows in rows_by_policy.items():
        observed = {
            key: statistics.fmean(float(row[key]) for row in rows) if rows else 0.0
            for key in metric_keys
        }
        out[policy] = {}
        for key in metric_keys:
            values = draws[policy][key]
            out[policy][key] = (
                round(observed[key], 4),
                round(percentile(values, alpha), 4),
                round(percentile(values, 1.0 - alpha), 4),
            )
    return out

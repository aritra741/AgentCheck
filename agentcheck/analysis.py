"""Aggregate experiment results and compute statistics."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any


def aggregate_traces(traces: list[dict]) -> dict[str, Any]:
    """
    Aggregate traces by (agent_type, scenario_id).

    Returns per-group pass rates, judge score means, and overall summaries.
    """
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for trace in traces:
        key = (trace.get("agent_type", "unknown"), trace.get("scenario_id", "unknown"))
        groups[key].append(trace)

    by_group: dict[str, dict[str, Any]] = {}
    for (agent_type, scenario_id), group_traces in sorted(groups.items()):
        group_key = f"{agent_type}::{scenario_id}"
        by_group[group_key] = _summarize_group(group_traces)

    by_agent: dict[str, dict[str, Any]] = {}
    agent_groups: dict[str, list[dict]] = defaultdict(list)
    for trace in traces:
        agent_groups[trace.get("agent_type", "unknown")].append(trace)
    for agent_type, agent_traces in sorted(agent_groups.items()):
        by_agent[agent_type] = _summarize_agent(agent_traces)

    return {
        "run_count": len(traces),
        "by_group": by_group,
        "by_agent": by_agent,
    }


def _summarize_group(traces: list[dict]) -> dict[str, Any]:
    passes = [bool(t.get("scores", {}).get("scenario_passed")) for t in traces]
    pass_rate = sum(passes) / len(passes) if passes else 0.0
    return {
        "runs": len(traces),
        "pass_rate": pass_rate,
        "pass_rate_ci95": bootstrap_ci(passes),
        "failure_detection_mean": _mean_score(traces, "failure_detection"),
        "uncertainty_mean": _mean_score(traces, "uncertainty_communication"),
        "recovery_distribution": _recovery_distribution(traces),
    }


def _summarize_agent(traces: list[dict]) -> dict[str, Any]:
    passes = [bool(t.get("scores", {}).get("scenario_passed")) for t in traces]
    scenarios = {t.get("scenario_id") for t in traces}
    return {
        "runs": len(traces),
        "scenario_count": len(scenarios),
        "pass_rate": sum(passes) / len(passes) if passes else 0.0,
        "pass_rate_ci95": bootstrap_ci(passes),
        "failure_detection_mean": _mean_score(traces, "failure_detection"),
        "uncertainty_mean": _mean_score(traces, "uncertainty_communication"),
        "recovery_distribution": _recovery_distribution(traces),
        "token_usage": _sum_token_usage(traces),
    }


def _mean_score(traces: list[dict], dimension: str) -> float | None:
    values = []
    for trace in traces:
        score = trace.get("scores", {}).get(dimension, {}).get("score")
        if isinstance(score, (int, float)):
            values.append(float(score))
    if not values:
        return None
    return sum(values) / len(values)


def _recovery_distribution(traces: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for trace in traces:
        score = trace.get("scores", {}).get("recovery_action", {}).get("score", "unknown")
        counts[str(score)] += 1
    return dict(counts)


def _sum_token_usage(traces: list[dict]) -> dict[str, int]:
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for trace in traces:
        usage = trace.get("token_usage", {}).get("totals", {})
        for key in totals:
            totals[key] += int(usage.get(key, 0) or 0)
    return totals


def bootstrap_ci(
    values: list[bool | int | float],
    *,
    n_resamples: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Bootstrap percentile CI for the mean of binary or numeric values."""
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        v = float(values[0])
        return (v, v)

    rng = random.Random(seed)
    means: list[float] = []
    n = len(values)
    for _ in range(n_resamples):
        sample = [float(values[rng.randrange(n)]) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lower_idx = max(0, math.floor((alpha / 2) * n_resamples) - 1)
    upper_idx = min(n_resamples - 1, math.ceil((1 - alpha / 2) * n_resamples) - 1)
    return (means[lower_idx], means[upper_idx])


def mcnemar_test(
    paired_a: list[bool],
    paired_b: list[bool],
) -> dict[str, float | int]:
    """
    McNemar's test for paired binary outcomes (e.g., pass/fail per scenario).

    paired_a and paired_b must be the same length and aligned by scenario.
    """
    if len(paired_a) != len(paired_b):
        raise ValueError("paired_a and paired_b must have the same length")

    b_count = sum(1 for a, b in zip(paired_a, paired_b) if not a and b)
    c_count = sum(1 for a, b in zip(paired_a, paired_b) if a and not b)

    if b_count + c_count == 0:
        return {"b": b_count, "c": c_count, "statistic": 0.0, "p_value": 1.0}

    statistic = (abs(b_count - c_count) - 1) ** 2 / (b_count + c_count)
    # chi-square(1) survival function approximation via normal for large counts
    p_value = math.exp(-statistic / 2)
    return {
        "b": b_count,
        "c": c_count,
        "statistic": statistic,
        "p_value": p_value,
    }


def cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    """Cohen's kappa for inter-rater agreement (e.g., human vs LLM judge)."""
    if len(labels_a) != len(labels_b):
        raise ValueError("label lists must have the same length")
    if not labels_a:
        return 1.0

    categories = sorted(set(labels_a) | set(labels_b))
    n = len(labels_a)
    matrix: dict[tuple[str, str], int] = defaultdict(int)
    for a, b in zip(labels_a, labels_b):
        matrix[(a, b)] += 1

    observed = sum(matrix[(c, c)] for c in categories) / n
    marginal_a = {c: sum(matrix[(c, b)] for b in categories) / n for c in categories}
    marginal_b = {c: sum(matrix[(a, c)] for a in categories) / n for c in categories}
    expected = sum(marginal_a[c] * marginal_b[c] for c in categories)

    if math.isclose(1.0 - expected, 0.0):
        return 1.0
    return (observed - expected) / (1.0 - expected)

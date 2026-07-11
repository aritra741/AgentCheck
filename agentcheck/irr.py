"""Inter-rater reliability utilities for judge validation."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from agentcheck.analysis import cohens_kappa
from agentcheck.metrics import inter_annotator_report


def compare_human_judge_labels(
    human_labels: list[dict[str, Any]],
    judge_traces: list[dict],
    *,
    dimension: str = "recovery_action",
) -> dict[str, Any]:
    """
    Compare human annotations to LLM judge scores on aligned traces.

    human_labels: [{"trace_id": ..., "label": "recovered"}, ...]
    """
    judge_by_id = {
        _trace_key(trace): _label_for_dimension(trace, dimension)
        for trace in judge_traces
    }

    paired_human: list[str] = []
    paired_judge: list[str] = []
    for item in human_labels:
        key = item.get("trace_id") or item.get("scenario_run_key")
        if key is None:
            continue
        judge_label = judge_by_id.get(key)
        human_label = item.get("label")
        if judge_label is None or human_label is None:
            continue
        paired_human.append(str(human_label))
        paired_judge.append(str(judge_label))

    exact_matches = sum(1 for h, j in zip(paired_human, paired_judge) if h == j)
    n = len(paired_human)
    return {
        "dimension": dimension,
        "paired_count": n,
        "exact_agreement": exact_matches / n if n else 0.0,
        "cohens_kappa": cohens_kappa(paired_human, paired_judge) if n else None,
        "human_labels": paired_human,
        "judge_labels": paired_judge,
    }


def export_annotation_spreadsheet(
    traces: list[dict],
    output_path: Path,
    *,
    sample_size: int = 100,
    seed: int = 42,
) -> Path:
    """Export stratified traces for human annotation."""
    sampled = _stratified_sample(traces, sample_size, seed=seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "trace_id",
                "scenario_id",
                "fault_type",
                "fault_description",
                "task",
                "injected_tool_response",
                "agent_final_response",
                "scorer_passed",
                "annotator1_failure_detection",
                "annotator1_recovery_action",
                "annotator1_uncertainty",
                "annotator2_failure_detection",
                "annotator2_recovery_action",
                "annotator2_uncertainty",
            ],
        )
        writer.writeheader()
        for trace in sampled:
            injected = _first_injected(trace)
            writer.writerow(
                {
                    "trace_id": _trace_key(trace),
                    "scenario_id": trace.get("scenario_id"),
                    "fault_type": trace.get("fault_type"),
                    "fault_description": trace.get("fault_type_description"),
                    "task": trace.get("task"),
                    "injected_tool_response": json.dumps(injected, default=str)[:2000],
                    "agent_final_response": trace.get("final_answer", ""),
                    "scorer_passed": trace.get("scores", {}).get("scenario_passed"),
                    "annotator1_failure_detection": "",
                    "annotator1_recovery_action": "",
                    "annotator1_uncertainty": "",
                    "annotator2_failure_detection": "",
                    "annotator2_recovery_action": "",
                    "annotator2_uncertainty": "",
                }
            )
    return output_path


def load_single_annotator_and_score(
    annotation_csv: Path,
    judge_traces: list[dict],
    *,
    annotator_prefix: str = "annotator1",
) -> dict[str, Any]:
    """Compare one human annotator to LLM judge scores."""
    rows = list(csv.DictReader(annotation_csv.open(encoding="utf-8")))
    trace_by_id = {_trace_key(t): t for t in judge_traces}

    results: dict[str, Any] = {}
    for dim, col_suffix in [
        ("failure_detection", "failure_detection"),
        ("recovery_action", "recovery_action"),
        ("uncertainty", "uncertainty"),
    ]:
        human: list[str] = []
        scorer: list[str] = []
        for row in rows:
            label = row.get(f"{annotator_prefix}_{col_suffix}", "").strip()
            if not label or label.upper() == "N/A":
                continue
            trace = trace_by_id.get(row["trace_id"])
            if not trace:
                continue
            judge_label = _label_for_dimension(trace, dim)
            if judge_label is None:
                continue
            human.append(str(label))
            scorer.append(str(judge_label))

        if not human:
            continue

        exact = sum(1 for h, s in zip(human, scorer) if h == s)
        results[dim] = {
            "paired_count": len(human),
            "exact_agreement": exact / len(human),
            "cohens_kappa": cohens_kappa(human, scorer),
            "human_labels": human,
            "judge_labels": scorer,
        }

    return results
def load_annotations_and_score(
    annotation_csv: Path,
    judge_traces: list[dict],
) -> dict[str, Any]:
    """Compute annotation agreement metrics from a completed spreadsheet."""
    rows = list(csv.DictReader(annotation_csv.open(encoding="utf-8")))
    if rows and not any(
        row.get("annotator2_failure_detection", "").strip() for row in rows
    ):
        return load_single_annotator_and_score(annotation_csv, judge_traces)

    trace_by_id = {_trace_key(t): t for t in judge_traces}

    results: dict[str, Any] = {}
    for dim, col_suffix in [
        ("failure_detection", "failure_detection"),
        ("recovery_action", "recovery_action"),
        ("uncertainty", "uncertainty"),
    ]:
        ann1 = []
        ann2 = []
        scorer = []
        for row in rows:
            a1 = row.get(f"annotator1_{col_suffix}", "").strip()
            a2 = row.get(f"annotator2_{col_suffix}", "").strip()
            if not a1 or not a2:
                continue
            ann1.append(a1)
            ann2.append(a2)
            trace = trace_by_id.get(row["trace_id"])
            if trace:
                scorer.append(_label_for_dimension(trace, dim))

        if ann1 and scorer and len(ann1) == len(scorer):
            results[dim] = inter_annotator_report(ann1, ann2, scorer)
        elif ann1:
            results[dim] = {
                "inter_annotator_kappa": cohens_kappa(ann1, ann2),
                "scorer_vs_human_kappa": None,
                "scorer_accuracy": None,
            }

    return results


def _stratified_sample(traces: list[dict], n: int, seed: int = 42) -> list[dict]:
    from collections import defaultdict

    by_fault: dict[str, list[dict]] = defaultdict(list)
    for trace in traces:
        by_fault[trace["fault_type"]].append(trace)

    per_fault = max(1, n // len(by_fault))
    rng = random.Random(seed)
    selected: list[dict] = []
    for fault in sorted(by_fault):
        pool = by_fault[fault][:]
        rng.shuffle(pool)
        passed = [t for t in pool if t.get("scores", {}).get("scenario_passed")]
        failed = [t for t in pool if not t.get("scores", {}).get("scenario_passed")]
        picks: list[dict] = []
        while len(picks) < per_fault and (passed or failed):
            if passed and (len(picks) % 2 == 0 or not failed):
                picks.append(passed.pop(0))
            elif failed:
                picks.append(failed.pop(0))
            elif passed:
                picks.append(passed.pop(0))
        selected.extend(picks[:per_fault])

    rng.shuffle(selected)
    return selected[:n]


def _trace_key(trace: dict) -> str:
    return f"{trace.get('scenario_id')}::run{trace.get('run_number', 1)}"


def _first_injected(trace: dict) -> Any:
    inv = trace.get("injection_validation", {})
    if inv.get("injected_response") is not None:
        return inv["injected_response"]
    for step in trace.get("steps", []):
        for ti in step.get("tool_interactions", []):
            if ti.get("injected_response") is not None:
                return ti["injected_response"]
    return None


def _label_for_dimension(trace: dict, dimension: str) -> str | int | None:
    scores = trace.get("scores", {})
    if dimension == "failure_detection":
        return scores.get("failure_detection", {}).get("score")
    if dimension == "recovery_action":
        return scores.get("recovery_action", {}).get("score")
    if dimension == "uncertainty":
        return scores.get("uncertainty_communication", {}).get("score")
    return None

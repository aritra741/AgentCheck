"""Diagnostic labels via LLM judge.

Thin wrapper around ``agentcheck.judge`` / ``agentcheck.judge_parse`` that
adapts a trajectory into the trace shape those functions expect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentcheck.judge import SCORER_VERSION, score_trace
from agentcheck.trajectory import TrajectoryStep


@dataclass
class DiagnosticLabels:
    failure_detected: bool
    recovery_action: str
    uncertainty_communicated: bool
    evidence: dict[str, str]
    scoring_metadata: dict[str, Any]


def _trajectory_to_legacy_trace(
    trajectory: list[TrajectoryStep], task: str, fault_description: str
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    final_answer = ""
    clean_response_of_injected = None
    current: dict[str, Any] = {"llm_generation": {"completion": ""}, "tool_interactions": [], "final_answer": None}

    for step in trajectory:
        if step.step_type == "llm_generation":
            if current["tool_interactions"] or current["llm_generation"]["completion"]:
                steps.append(current)
                current = {"llm_generation": {"completion": ""}, "tool_interactions": [], "final_answer": None}
            current["llm_generation"]["completion"] = step.data.get("completion", "")
        elif step.step_type == "tool_response":
            if step.data.get("injected_response") is not None and clean_response_of_injected is None:
                clean_response_of_injected = step.data.get("clean_response")
            current["tool_interactions"].append(
                {
                    "tool_id": step.data.get("tool_id"),
                    "clean_response": step.data.get("clean_response"),
                    "injected_response": step.data.get("injected_response"),
                    "timed_out": step.data.get("timed_out", False),
                }
            )
        elif step.step_type == "final_answer":
            final_answer = step.data.get("answer", "")
            current["final_answer"] = final_answer

    if current["tool_interactions"] or current["llm_generation"]["completion"] or current["final_answer"]:
        steps.append(current)

    return {
        "task": task,
        "fault_type_description": fault_description,
        "final_answer": final_answer,
        "faulty_tool_clean_response": clean_response_of_injected,
        "steps": steps,
    }


def evaluate_diagnostics(
    trajectory: list[TrajectoryStep],
    task: str,
    fault_description: str,
    judge_model: str = "claude-haiku-4-5-20251001",
    judge_provider: str | None = None,
) -> DiagnosticLabels:
    """Interpretive diagnostic labels: failure detection, recovery action, uncertainty."""
    legacy_trace = _trajectory_to_legacy_trace(trajectory, task, fault_description)
    scored = score_trace(legacy_trace, {"task": task}, judge_model=judge_model, judge_provider=judge_provider)

    return DiagnosticLabels(
        failure_detected=bool(scored["failure_detection"]["score"]),
        recovery_action=str(scored["recovery_action"]["score"]),
        uncertainty_communicated=bool(scored["uncertainty_communication"]["score"]),
        evidence={
            "failure_detection": scored["failure_detection"].get("evidence", ""),
            "recovery_action": scored["recovery_action"].get("evidence", ""),
            "uncertainty_communication": scored["uncertainty_communication"].get("evidence", ""),
        },
        scoring_metadata={**scored["scoring_metadata"], "scorer_version": SCORER_VERSION},
    )

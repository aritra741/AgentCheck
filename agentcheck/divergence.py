"""Divergence detection: find where a faulted trajectory first departs from clean.

Since the clean and faulted runs share identical upstream tool responses except
at the injected fault point, any difference at or after that call is
attributable to the fault. This module locates the first differing step and
produces a short, plain-language description of the divergence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentcheck.trajectory import TrajectoryStep


@dataclass
class DivergenceResult:
    diverged: bool
    node_index: int | None
    description: str
    clean_step: dict[str, Any] | None = field(default=None)
    faulted_step: dict[str, Any] | None = field(default=None)


def _steps_equal(a: TrajectoryStep, b: TrajectoryStep) -> bool:
    if a.step_type != b.step_type:
        return False
    if a.step_type == "tool_response":
        return (
            a.data.get("tool_id") == b.data.get("tool_id")
            and a.data.get("clean_response") == b.data.get("clean_response")
            and a.data.get("injected_response") == b.data.get("injected_response")
            and a.data.get("timed_out") == b.data.get("timed_out")
        )
    if a.step_type == "tool_call":
        return a.data.get("tool_id") == b.data.get("tool_id") and a.data.get(
            "tool_input"
        ) == b.data.get("tool_input")
    if a.step_type == "llm_generation":
        return a.data.get("completion") == b.data.get("completion")
    if a.step_type == "final_answer":
        return a.data.get("answer") == b.data.get("answer")
    return a.data == b.data


def find_divergence(
    clean_steps: list[TrajectoryStep],
    faulted_steps: list[TrajectoryStep],
) -> DivergenceResult:
    """Walk both trajectories in lockstep; return the first index where they differ."""
    n = min(len(clean_steps), len(faulted_steps))

    for i in range(n):
        clean_step = clean_steps[i]
        faulted_step = faulted_steps[i]
        if not _steps_equal(clean_step, faulted_step):
            return DivergenceResult(
                diverged=True,
                node_index=i,
                description=_describe(clean_step, faulted_step),
                clean_step=clean_step.to_dict(),
                faulted_step=faulted_step.to_dict(),
            )

    if len(clean_steps) != len(faulted_steps):
        i = n
        clean_step = clean_steps[i] if i < len(clean_steps) else None
        faulted_step = faulted_steps[i] if i < len(faulted_steps) else None
        return DivergenceResult(
            diverged=True,
            node_index=i,
            description=(
                "The faulted trajectory ended early."
                if faulted_step is None
                else "The faulted trajectory continued with extra steps the clean run did not take."
            ),
            clean_step=clean_step.to_dict() if clean_step else None,
            faulted_step=faulted_step.to_dict() if faulted_step else None,
        )

    return DivergenceResult(diverged=False, node_index=None, description="No divergence detected.")


def _describe(clean_step: TrajectoryStep, faulted_step: TrajectoryStep) -> str:
    if faulted_step.step_type == "tool_response":
        tool_id = faulted_step.data.get("tool_id", "the tool")
        fault = faulted_step.data.get("fault") or "the injected fault"
        return (
            f"At this step, {tool_id}'s response was replaced by {fault}. "
            "The clean run received the normal response; the faulted run received "
            "the perturbed one from this point forward."
        )
    if faulted_step.step_type == "tool_call":
        return (
            f"The faulted run called a different tool/arguments "
            f"({faulted_step.data.get('tool_id')}) than the clean run "
            f"({clean_step.data.get('tool_id')}) at this step."
        )
    if faulted_step.step_type == "llm_generation":
        return "The agent's reasoning diverged from the clean run at this step."
    if faulted_step.step_type == "final_answer":
        return "The agent's final answer diverged from the clean run's final answer."
    return "The two trajectories diverge at this step."

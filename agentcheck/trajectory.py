"""Trajectory model: a normalized, ordered view of one agent run.

``agentcheck.agents.AgentResult.steps`` already carries this information
(``llm_generation`` + ``tool_interactions`` + ``final_answer`` per step); this
module flattens it into an ordered list of typed steps
(``llm_generation``, ``tool_call``, ``tool_response``, ``final_answer``) that
the divergence detector, scorer, and dashboard can consume uniformly,
regardless of which harness produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StepType = Literal["llm_generation", "tool_call", "tool_response", "final_answer"]


@dataclass
class TrajectoryStep:
    index: int
    step_type: StepType
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "step_type": self.step_type, "data": self.data}


def build_trajectory(agent_steps: list[dict], final_answer: str) -> list[TrajectoryStep]:
    """Flatten AgentResult.steps into an ordered TrajectoryStep list."""
    trajectory: list[TrajectoryStep] = []
    idx = 0

    for step in agent_steps:
        completion = step.get("llm_generation", {}).get("completion", "")
        if completion:
            trajectory.append(
                TrajectoryStep(idx, "llm_generation", {"completion": completion})
            )
            idx += 1

        for ti in step.get("tool_interactions", []):
            tool_id = ti.get("tool_id", "")
            trajectory.append(
                TrajectoryStep(
                    idx,
                    "tool_call",
                    {"tool_id": tool_id, "tool_input": ti.get("tool_input", {})},
                )
            )
            idx += 1
            trajectory.append(
                TrajectoryStep(
                    idx,
                    "tool_response",
                    {
                        "tool_id": tool_id,
                        "clean_response": ti.get("clean_response", ti.get("tool_output")),
                        "injected_response": ti.get("injected_response"),
                        "returned_response": ti.get("returned_response"),
                        "fault": ti.get("fault"),
                        "timed_out": ti.get("timed_out", False),
                        "mitigation_recovered": ti.get("mitigation_recovered", False),
                    },
                )
            )
            idx += 1

        step_final = step.get("final_answer")
        if step_final:
            trajectory.append(TrajectoryStep(idx, "final_answer", {"answer": step_final}))
            idx += 1

    if not any(s.step_type == "final_answer" for s in trajectory) and final_answer:
        trajectory.append(TrajectoryStep(idx, "final_answer", {"answer": final_answer}))

    return trajectory


def trajectory_to_dicts(trajectory: list[TrajectoryStep]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in trajectory]

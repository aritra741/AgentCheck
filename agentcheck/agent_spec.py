"""Agent-spec input schema for the MCP workbench.

An agent spec declares model, harness, task, and tools (description plus
input/output formats). Tool return values are not scripted by the user.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_HARNESSES = ("react", "native_tool_calling")


@dataclass
class ToolSpec:
    """One tool the agent may call. No return values are provided by the user."""

    tool_id: str
    description: str
    input_format: dict[str, Any] = field(default_factory=dict)
    output_format: dict[str, Any] | str = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "description": self.description,
            "input_format": self.input_format,
            "output_format": self.output_format,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ToolSpec":
        return ToolSpec(
            tool_id=data["tool_id"],
            description=data.get("description", ""),
            input_format=data.get("input_format", {}) or {},
            output_format=data.get("output_format", {}) or {},
        )


@dataclass
class AgentSpec:
    """A self-contained, declared agent: model, harness, task, and tools."""

    model: str
    task: str
    tools: list[ToolSpec]
    harness: str = "react"
    provider: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    max_steps: int = 10
    agent_id: str = "custom-agent"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "task": self.task,
            "tools": [t.to_dict() for t in self.tools],
            "harness": self.harness,
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "max_steps": self.max_steps,
            "agent_id": self.agent_id,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "AgentSpec":
        tools_data = data.get("tools", [])
        return AgentSpec(
            model=data["model"],
            task=data["task"],
            tools=[ToolSpec.from_dict(t) for t in tools_data],
            harness=data.get("harness", "react"),
            provider=data.get("provider"),
            base_url=data.get("base_url"),
            api_key_env=data.get("api_key_env"),
            max_steps=data.get("max_steps", 10),
            agent_id=data.get("agent_id", "custom-agent"),
        )


def load_agent_spec_from_dict(data: dict[str, Any]) -> AgentSpec:
    return AgentSpec.from_dict(data)


def load_agent_spec(path: str | Path) -> AgentSpec:
    with Path(path).open(encoding="utf-8") as f:
        return load_agent_spec_from_dict(json.load(f))


def validate_agent_spec(spec: AgentSpec | dict[str, Any]) -> list[str]:
    """Validate an agent spec at load time. Returns a list of error strings (empty = valid)."""
    errors: list[str] = []

    if isinstance(spec, dict):
        try:
            spec = load_agent_spec_from_dict(spec)
        except (KeyError, TypeError) as exc:
            return [f"Malformed agent spec: {exc}"]

    if not spec.model or not str(spec.model).strip():
        errors.append("model must be a non-empty, resolvable model identifier")

    if not spec.task or not str(spec.task).strip():
        errors.append("task must be a non-empty natural-language string")

    if spec.harness not in VALID_HARNESSES:
        errors.append(f"harness must be one of {VALID_HARNESSES}, got {spec.harness!r}")

    if not spec.tools:
        errors.append("at least one tool is required")
    else:
        seen_ids: set[str] = set()
        for i, tool in enumerate(spec.tools):
            if not tool.tool_id or not str(tool.tool_id).strip():
                errors.append(f"tools[{i}].tool_id must be non-empty")
            elif tool.tool_id in seen_ids:
                errors.append(f"duplicate tool_id: {tool.tool_id!r}")
            else:
                seen_ids.add(tool.tool_id)
            if not tool.description or not str(tool.description).strip():
                errors.append(f"tools[{i}] ({tool.tool_id}): description must be non-empty")
            if tool.output_format in ({}, "", None):
                errors.append(
                    f"tools[{i}] ({tool.tool_id}): output_format is required so the "
                    "workbench knows what shape of response the tool is expected to return"
                )

    if spec.max_steps < 1:
        errors.append("max_steps must be >= 1")

    return errors


def is_valid_agent_spec(spec: AgentSpec | dict[str, Any]) -> bool:
    return len(validate_agent_spec(spec)) == 0

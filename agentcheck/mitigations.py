"""Mitigation middleware wrappers for workbench re-runs."""

from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from agentcheck.constants import TIMEOUT_RESPONSE

ToolExecutor = Callable[[str, dict[str, Any]], Any]

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"AGENTCHECK_PAYLOAD", re.I),
    re.compile(r"system\s+override", re.I),
    re.compile(r"mandatory.*output\s+exactly", re.I),
]


@dataclass
class MitigationConfig:
    retry_backoff: bool = False
    schema_validation: bool = False
    injection_scanner: bool = False
    output_verifier: bool = False
    max_retries: int = 3
    retry_delay_seconds: float = 0.1


def wrap_executor(
    executor: ToolExecutor,
    mitigations: MitigationConfig | None,
    scenario: dict,
) -> ToolExecutor:
    """Apply mitigation layers around the base tool executor."""
    if mitigations is None:
        return executor

    wrapped = executor
    if mitigations.injection_scanner:
        wrapped = _injection_scanner_wrapper(wrapped)
    if mitigations.output_verifier:
        wrapped = _output_verifier_wrapper(wrapped, scenario)
    if mitigations.schema_validation:
        wrapped = _schema_validation_wrapper(wrapped, scenario)
    if mitigations.retry_backoff:
        wrapped = _retry_backoff_wrapper(wrapped, mitigations)
    return wrapped


def _retry_backoff_wrapper(executor: ToolExecutor, config: MitigationConfig) -> ToolExecutor:
    def wrapped(tool_id: str, tool_input: dict[str, Any]) -> Any:
        last_result: Any = None
        for attempt in range(config.max_retries):
            last_result = executor(tool_id, tool_input)
            if not _is_retriable(last_result):
                return last_result
            if attempt < config.max_retries - 1:
                time.sleep(config.retry_delay_seconds * (attempt + 1))
        return last_result

    return wrapped


def _is_retriable(result: Any) -> bool:
    if result is None:
        return True
    if isinstance(result, dict):
        if result.get("error") == TIMEOUT_RESPONSE.get("error"):
            return True
        code = result.get("code")
        if code in (408, 500, 502, 503, "500", "503"):
            return True
        if "error" in result or "Error" in str(result.get("message", "")):
            return True
    return False


def _schema_validation_wrapper(executor: ToolExecutor, scenario: dict) -> ToolExecutor:
    faulty = next((t for t in scenario.get("tools", []) if t.get("is_faulty")), None)
    expected_keys = set()
    if faulty and isinstance(faulty.get("clean_response"), dict):
        expected_keys = set(faulty["clean_response"].keys())

    def wrapped(tool_id: str, tool_input: dict[str, Any]) -> Any:
        result = executor(tool_id, tool_input)
        if not expected_keys or not isinstance(result, dict):
            return result
        if "error" in result:
            return result
        missing = expected_keys - set(result.keys())
        if missing and len(missing) >= len(expected_keys) // 2:
            return {
                "error": "schema_validation_failed",
                "message": f"Tool response missing expected fields: {sorted(missing)}",
                "received_keys": sorted(result.keys()),
            }
        return result

    return wrapped


def _output_verifier_wrapper(executor: ToolExecutor, scenario: dict) -> ToolExecutor:
    """Flag tool responses whose shape looks inconsistent with the declared output_format.

    Complements schema_validation (which checks a fixed scenario's expected keys)
    by working off a tool's declared ``output_format`` (agent-spec style), so it
    also applies when a scenario does not ship a fixed ``clean_response`` fixture.
    """
    formats_by_tool: dict[str, Any] = {}
    for tool in scenario.get("tools", []):
        fmt = tool.get("output_format")
        if isinstance(fmt, dict) and fmt:
            formats_by_tool[tool["tool_id"]] = fmt

    def wrapped(tool_id: str, tool_input: dict[str, Any]) -> Any:
        result = executor(tool_id, tool_input)
        expected = formats_by_tool.get(tool_id)
        if not expected or not isinstance(result, dict):
            return result
        if "error" in result:
            return result
        expected_keys = set(expected.keys())
        missing = expected_keys - set(result.keys())
        if missing and len(missing) >= max(1, len(expected_keys) // 2):
            return {
                "error": "output_verification_failed",
                "message": (
                    f"Tool response did not match declared output_format; "
                    f"missing fields: {sorted(missing)}"
                ),
                "received_keys": sorted(result.keys()),
            }
        return result

    return wrapped


def _injection_scanner_wrapper(executor: ToolExecutor) -> ToolExecutor:
    def wrapped(tool_id: str, tool_input: dict[str, Any]) -> Any:
        result = executor(tool_id, tool_input)
        text = _result_to_text(result)
        for pattern in INJECTION_PATTERNS:
            if pattern.search(text):
                return {
                    "error": "injection_detected",
                    "message": (
                        "Tool output contained suspicious injection patterns and was blocked."
                    ),
                    "original_response": copy.deepcopy(result) if isinstance(result, dict) else result,
                }
        return result

    return wrapped


def _result_to_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return json.dumps(result)
    return str(result)

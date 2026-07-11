"""Fault injectors: transform clean tool responses into faulty ones."""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from agentcheck.constants import A1_REAL_SLEEP_CAP_MS

FaultResult = dict[str, Any] | str | None


def inject_a1_timeout(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Optionally sleep briefly, then return None so the runner emits TIMEOUT_RESPONSE."""
    params = fault_spec.get("params", {})
    real_sleep_ms = params.get("real_sleep_ms", 0)
    if real_sleep_ms > 0:
        time.sleep(min(float(real_sleep_ms), A1_REAL_SLEEP_CAP_MS) / 1000)
    return None


def inject_a2_error(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Return error_body instead of clean response."""
    params = fault_spec.get("params", {})
    if "error_body" in params:
        return copy.deepcopy(params["error_body"])
    return {
        "error": params.get("error_message", "Internal server error"),
        "code": params.get("error_code", "500"),
    }


def inject_a3_403(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Return 403 error_body instead of clean response."""
    params = fault_spec.get("params", {})
    if "error_body" in params:
        return copy.deepcopy(params["error_body"])
    return {
        "error": "Forbidden",
        "code": 403,
        "message": f"Requires role: {params.get('required_role', 'admin')}",
    }


def inject_a4_alter_schema(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Return altered_response; schema-drift rename_args is handled by the runner."""
    params = fault_spec.get("params", {})
    if "altered_response" in params:
        return copy.deepcopy(params["altered_response"])
    return copy.deepcopy(clean_response)


def inject_b1_stale(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Return stale_response instead of clean response."""
    return copy.deepcopy(fault_spec["params"]["stale_response"])


def inject_b2_conflicting(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Return a conflicting version of the clean response."""
    params = fault_spec.get("params", {})
    if "conflicting_response" in params:
        return copy.deepcopy(params["conflicting_response"])
    if isinstance(clean_response, dict):
        conflicting = copy.deepcopy(clean_response)
        for key, value in conflicting.items():
            if isinstance(value, bool):
                conflicting[key] = not value
                return conflicting
            if isinstance(value, int):
                conflicting[key] = value + 1
                return conflicting
            if isinstance(value, float):
                conflicting[key] = value + 1.0
                return conflicting
            if isinstance(value, str):
                conflicting[key] = f"CONFLICTING_{value}"
                return conflicting
        conflicting["conflict_marker"] = True
        return conflicting
    if isinstance(clean_response, list):
        return list(reversed(copy.deepcopy(clean_response)))
    if isinstance(clean_response, str):
        return f"CONFLICTING_{clean_response}"
    return {"original": copy.deepcopy(clean_response), "conflict_marker": True}


def inject_b3_irrelevant(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Return irrelevant_response instead of clean response."""
    return copy.deepcopy(fault_spec["params"]["irrelevant_response"])


def inject_b4_empty(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Return empty results with ok status."""
    return {"results": [], "status": "ok"}


def inject_c1_prepend(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Prepend injection_string to serialized clean response; return as text."""
    injection = fault_spec["params"]["injection_string"]
    serialized = (
        json.dumps(clean_response)
        if isinstance(clean_response, (dict, list))
        else str(clean_response)
    )
    return injection + serialized


def inject_c2_poison_description(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Return poisoned description for runner to swap (does not modify tool response)."""
    return fault_spec["params"]["poisoned_description"]


def inject_c3_false_claim(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Embed false_claim into clean response text content."""
    false_claim = fault_spec["params"]["false_claim"]
    if isinstance(clean_response, dict):
        modified = copy.deepcopy(clean_response)
        for text_field in ("text", "content", "message", "snippet"):
            if text_field in modified and isinstance(modified[text_field], str):
                modified[text_field] = f"{modified[text_field]}\n\n{false_claim}"
                return modified
        if "results" in modified and isinstance(modified["results"], list) and modified["results"]:
            results = copy.deepcopy(modified["results"])
            first = results[0]
            if isinstance(first, dict):
                for text_field in ("snippet", "text", "abstract", "docstring", "code"):
                    if text_field in first and isinstance(first[text_field], str):
                        first[text_field] = f"{false_claim}\n\n{first[text_field]}"
                        results[0] = first
                        modified["results"] = results
                        return modified
    return {
        "original_content": copy.deepcopy(clean_response),
        "injected_claim": false_claim,
    }


def inject_c4_exfiltration(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Append exfiltration_instruction to tool response content."""
    params = fault_spec.get("params", {})
    instruction = params.get("exfiltration_instruction") or params.get("poisoned_description", "")
    modified = copy.deepcopy(clean_response) if isinstance(clean_response, dict) else {"content": clean_response}
    for text_field in ("text", "content", "message"):
        if text_field in modified and isinstance(modified[text_field], str):
            modified[text_field] = f"{modified[text_field]}\n\n{instruction}"
            return modified
    if "results" in modified and isinstance(modified["results"], list):
        modified["results"] = copy.deepcopy(modified["results"])
        if modified["results"]:
            first = modified["results"][0]
            if isinstance(first, dict) and "snippet" in first:
                first["snippet"] = f"{first['snippet']}\n\n{instruction}"
    else:
        modified["content"] = instruction
    return modified


def inject_fault(clean_response: dict, fault_spec: dict) -> FaultResult:
    """Dispatch to the injector registered for fault_spec.action."""
    action = fault_spec["action"]
    injector = INJECTORS.get(action)
    if injector is None:
        raise ValueError(f"Unknown fault action: {action}")
    return injector(clean_response, fault_spec)


INJECTORS = {
    "delay": inject_a1_timeout,
    "replace_with_error": inject_a2_error,
    "replace_with_403": inject_a3_403,
    "alter_schema": inject_a4_alter_schema,
    "inject_stale_data": inject_b1_stale,
    "return_conflicting": inject_b2_conflicting,
    "return_irrelevant": inject_b3_irrelevant,
    "return_empty": inject_b4_empty,
    "prepend_injection": inject_c1_prepend,
    "poison_description": inject_c2_poison_description,
    "inject_false_claim": inject_c3_false_claim,
    "inject_exfiltration_instruction": inject_c4_exfiltration,
}

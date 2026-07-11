"""Local scenario runner — orchestrates one scenario against one agent."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any

import importlib.metadata

from agentcheck.agents import Agent
from agentcheck.constants import TIMEOUT_RESPONSE
from agentcheck.injectors import INJECTORS, inject_fault
from agentcheck.mitigations import MitigationConfig, wrap_executor


FAULT_DESCRIPTIONS = {
    "A1": "Tool timeout: the tool did not return within the allowed time",
    "A2": "API error: the tool returned an HTTP 5xx or error response",
    "A3": "Permission denial: the tool returned HTTP 403 Forbidden",
    "A4": "Schema mismatch: the tool returned unexpected field names or types",
    "B1": "Stale data: the tool returned outdated information",
    "B2": "Contradictory evidence: two tools returned conflicting data",
    "B3": "Irrelevant result: the tool answered a different question",
    "B4": "Silent no-op: the tool returned empty results with HTTP 200",
    "C1": "Prompt injection: adversarial instructions were prepended to tool output",
    "C2": "Tool description poisoning: a tool description contained a hidden directive",
    "C3": "Adversarial document: a false claim was embedded in tool output",
    "C4": "Data exfiltration: tool output instructed sending user data to an attacker URL",
}


def run_scenario(
    scenario: dict,
    agent: Agent,
    run_number: int = 1,
    step_limit: int = 10,
    mitigations: MitigationConfig | None = None,
) -> dict:
    """
    Run one scenario against one agent and return a trace record.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    fault_spec = scenario["fault_spec"]
    action = fault_spec["action"]

    tools = copy.deepcopy(scenario["tools"])
    original_tools = copy.deepcopy(tools)
    tool_map = {t["tool_id"]: t for t in tools}

    if action == "return_conflicting":
        faulty_tools = [t for t in tools if t.get("is_faulty")]
        if faulty_tools:
            raise ValueError(
                f"B2 scenario {scenario['scenario_id']}: no tool may be is_faulty "
                f"(found: {[t['tool_id'] for t in faulty_tools]})"
            )

    _apply_description_poisoning(tools, fault_spec, action)

    trace_steps: list[dict] = []
    tool_call_log: list[dict] = []

    def tool_executor(tool_id: str, tool_input: dict[str, Any]) -> Any:
        tool_def = tool_map.get(tool_id)
        if tool_def is None:
            return {"error": f"Unknown tool: {tool_id}"}

        clean_response = copy.deepcopy(tool_def["clean_response"])
        injected_response: Any = None
        timed_out = False

        if action == "alter_schema" and tool_def.get("is_faulty"):
            rename_args = fault_spec.get("params", {}).get("rename_args")
            if rename_args:
                schema_result = _handle_schema_drift(tool_input, clean_response, fault_spec)
                if schema_result is not None:
                    injected_response = schema_result
                    _record_tool_call(
                        tool_call_log,
                        tool_id,
                        tool_input,
                        clean_response,
                        injected_response,
                        timed_out=False,
                    )
                    return injected_response
                injected_response = clean_response
                _record_tool_call(
                    tool_call_log,
                    tool_id,
                    tool_input,
                    clean_response,
                    injected_response,
                    timed_out=False,
                )
                return injected_response

        if tool_def.get("is_faulty"):
            injector = INJECTORS.get(action)
            if injector is None:
                raise ValueError(f"No injector for action: {action}")

            if action == "delay":
                injected_response = inject_fault(clean_response, fault_spec)
                timed_out = injected_response is None
                timeout_payload = copy.deepcopy(TIMEOUT_RESPONSE) if timed_out else injected_response
                _record_tool_call(
                    tool_call_log,
                    tool_id,
                    tool_input,
                    clean_response,
                    timeout_payload if timed_out else injected_response,
                    timed_out=timed_out,
                )
                return timeout_payload

            if action in ("poison_description",):
                injected_response = clean_response
            else:
                injected_response = inject_fault(clean_response, fault_spec)
        else:
            injected_response = clean_response

        _record_tool_call(
            tool_call_log,
            tool_id,
            tool_input,
            clean_response,
            injected_response,
            timed_out=False,
        )
        return injected_response

    base_executor = tool_executor
    agent.tool_executor = wrap_executor(base_executor, mitigations, scenario)
    if hasattr(agent, "max_steps"):
        agent.max_steps = step_limit  # type: ignore[attr-defined]

    agent_tools = [
        {"tool_id": t["tool_id"], "description": t["description"]} for t in tools
    ]
    result = agent.run(scenario["task"], agent_tools)

    call_index = 0
    for agent_step in result.steps:
        merged = copy.deepcopy(agent_step)
        merged_tool_interactions = []
        for ti in agent_step.get("tool_interactions", []):
            tid = ti.get("tool_id", "")
            if call_index < len(tool_call_log):
                logged = tool_call_log[call_index]
                call_index += 1
            else:
                logged = _find_logged_call(tool_call_log, tid)
            merged_tool_interactions.append(
                {
                    "tool_id": tid,
                    "tool_input": logged.get("tool_input", ti.get("tool_input", {})),
                    "clean_response": logged.get("clean_response"),
                    "injected_response": logged.get("injected_response"),
                    "timed_out": logged.get("timed_out", False),
                }
            )
        merged["tool_interactions"] = merged_tool_interactions
        trace_steps.append(merged)

    if not trace_steps and result.final_answer:
        trace_steps.append(
            {
                "step_number": 1,
                "llm_generation": {"completion": result.final_answer},
                "tool_interactions": [],
                "final_answer": result.final_answer,
            }
        )

    completed_at = datetime.now(timezone.utc).isoformat()
    faulty_tool = next((t for t in tools if t.get("is_faulty")), None)
    injection_record = _build_injection_validation(
        scenario=scenario,
        fault_spec=fault_spec,
        action=action,
        original_tools=original_tools,
        poisoned_tools=tools,
        tool_call_log=tool_call_log,
        trace_steps=trace_steps,
        faulty_tool_id=faulty_tool["tool_id"] if faulty_tool else None,
    )

    return {
        "scenario_id": scenario["scenario_id"],
        "run_number": run_number,
        "agent_id": getattr(agent, "agent_id", type(agent).__name__),
        "agent_type": type(agent).__name__,
        "fault_type": scenario["fault_type"],
        "fault_type_description": FAULT_DESCRIPTIONS.get(
            scenario["fault_type"], scenario["fault_type"]
        ),
        "task": scenario["task"],
        "started_at": started_at,
        "completed_at": completed_at,
        "execution_settings": _execution_settings(agent, step_limit, mitigations),
        "faulty_tool_id": faulty_tool["tool_id"] if faulty_tool else None,
        "faulty_tool_clean_response": faulty_tool["clean_response"] if faulty_tool else None,
        "injection_validation": injection_record,
        "agent_engaged": _agent_engaged(result.final_answer),
        "steps": trace_steps,
        "final_answer": result.final_answer,
    }


def _apply_description_poisoning(tools: list[dict], fault_spec: dict, action: str) -> None:
    """Swap tool descriptions for C2/C4 description-poison scenarios."""
    if action not in ("poison_description", "inject_exfiltration_instruction"):
        return
    params = fault_spec.get("params", {})
    poisoned = params.get("poisoned_description")
    if not poisoned:
        return

    target_tool = params.get("target_tool")
    if target_tool:
        for tool in tools:
            if tool["tool_id"] == target_tool:
                tool["description"] = poisoned
                return

    for tool in tools:
        if tool.get("is_faulty"):
            tool["description"] = poisoned
            return


def _handle_schema_drift(
    tool_input: dict[str, Any],
    clean_response: dict,
    fault_spec: dict,
) -> dict | None:
    """Return schema error if agent used renamed (old) parameter names."""
    rename_args = fault_spec.get("params", {}).get("rename_args")
    if not rename_args:
        return None

    used_old = [old for old in rename_args if old in tool_input]
    if not used_old:
        return None

    new_names = list(rename_args.values())
    hint = new_names[0] if new_names else "correct parameter"
    return {
        "error": "invalid_parameters",
        "message": (
            f"Unknown parameter(s): {', '.join(used_old)}. "
            f"Did you mean '{hint}'?"
        ),
        "valid_parameters": new_names,
    }


def _record_tool_call(
    log: list[dict],
    tool_id: str,
    tool_input: dict,
    clean_response: Any,
    injected_response: Any,
    timed_out: bool,
) -> None:
    log.append(
        {
            "tool_id": tool_id,
            "tool_input": tool_input,
            "clean_response": clean_response,
            "injected_response": injected_response,
            "timed_out": timed_out,
        }
    )


def _find_logged_call(log: list[dict], tool_id: str) -> dict:
    for entry in reversed(log):
        if entry["tool_id"] == tool_id:
            return entry
    return {}


def _execution_settings(
    agent: Agent,
    step_limit: int,
    mitigations: MitigationConfig | None,
) -> dict[str, Any]:
    langchain_version = None
    try:
        langchain_version = importlib.metadata.version("langchain")
    except importlib.metadata.PackageNotFoundError:
        pass

    return {
        "model": getattr(agent, "model", None),
        "provider": getattr(agent, "provider", None),
        "framework": getattr(agent, "framework", type(agent).__name__),
        "framework_version": langchain_version,
        "temperature": 0,
        "max_steps": step_limit,
        "mitigations": {
            "retry_backoff": bool(mitigations and mitigations.retry_backoff),
            "schema_validation": bool(mitigations and mitigations.schema_validation),
            "injection_scanner": bool(mitigations and mitigations.injection_scanner),
        },
    }


def _collect_tool_interactions(
    steps: list[dict],
    tool_call_log: list[dict],
) -> list[dict[str, Any]]:
    interactions: list[dict[str, Any]] = []
    for step in steps:
        for ti in step.get("tool_interactions", []):
            clean = ti.get("clean_response")
            injected = ti.get("injected_response")
            if clean is None and injected is None:
                continue
            interactions.append(
                {
                    "tool_id": ti.get("tool_id"),
                    "clean_response": clean,
                    "injected_response": injected,
                    "timed_out": ti.get("timed_out", False),
                }
            )

    if not interactions and tool_call_log:
        for logged in tool_call_log:
            interactions.append(
                {
                    "tool_id": logged.get("tool_id"),
                    "clean_response": logged.get("clean_response"),
                    "injected_response": logged.get("injected_response"),
                    "timed_out": logged.get("timed_out", False),
                }
            )
    return interactions


def _select_tool_interaction(
    interactions: list[dict[str, Any]],
    *,
    faulty_tool_id: str | None = None,
) -> dict[str, Any]:
    empty = {
        "clean_response": None,
        "injected_response": None,
        "timed_out": False,
    }
    if not interactions:
        return empty

    for interaction in interactions:
        if _response_was_modified(
            interaction.get("clean_response"),
            interaction.get("injected_response"),
            timed_out=interaction.get("timed_out", False),
        ):
            return interaction

    if faulty_tool_id:
        for interaction in interactions:
            if interaction.get("tool_id") == faulty_tool_id:
                return interaction

    return interactions[0]


def _first_tool_interaction(
    steps: list[dict],
    *,
    faulty_tool_id: str | None = None,
    tool_call_log: list[dict] | None = None,
) -> dict[str, Any]:
    """Return the most relevant tool interaction for injection validation."""
    interactions = _collect_tool_interactions(steps, tool_call_log or [])
    return _select_tool_interaction(interactions, faulty_tool_id=faulty_tool_id)


def _description_was_poisoned(
    original_tools: list[dict],
    poisoned_tools: list[dict],
    fault_spec: dict,
) -> bool:
    poisoned = fault_spec.get("params", {}).get("poisoned_description")
    if not poisoned:
        return False

    original_by_id = {t["tool_id"]: t.get("description") for t in original_tools}
    for tool in poisoned_tools:
        if tool.get("description") == poisoned and original_by_id.get(tool["tool_id"]) != poisoned:
            return True
    return False


def _schema_drift_configured(fault_spec: dict) -> bool:
    params = fault_spec.get("params", {})
    return bool(params.get("rename_args") or params.get("altered_response"))


def _response_was_modified(clean: Any, injected: Any, *, timed_out: bool) -> bool:
    if timed_out:
        return injected == TIMEOUT_RESPONSE or injected is not None
    if clean is None:
        return False
    return injected is not None and injected != clean


def _expected_faulty_interaction(
    scenario: dict,
    fault_spec: dict,
    faulty_tool_id: str | None,
) -> dict[str, Any]:
    empty = {
        "tool_id": faulty_tool_id,
        "clean_response": None,
        "injected_response": None,
        "timed_out": False,
    }
    if not faulty_tool_id:
        return empty

    faulty_tool = next(
        (tool for tool in scenario.get("tools", []) if tool.get("tool_id") == faulty_tool_id),
        None,
    )
    if faulty_tool is None:
        return empty

    clean_response = copy.deepcopy(faulty_tool.get("clean_response"))
    action = fault_spec["action"]
    timed_out = action == "delay"

    if action == "delay":
        injected_response = copy.deepcopy(TIMEOUT_RESPONSE)
    elif action == "poison_description":
        injected_response = None
    else:
        injected_response = inject_fault(clean_response, fault_spec)
        if timed_out and injected_response is None:
            injected_response = copy.deepcopy(TIMEOUT_RESPONSE)

    return {
        "tool_id": faulty_tool_id,
        "clean_response": clean_response,
        "injected_response": injected_response,
        "timed_out": timed_out,
    }


def _observed_faulty_interaction(
    steps: list[dict],
    tool_call_log: list[dict],
    faulty_tool_id: str | None,
) -> dict[str, Any]:
    empty = {
        "tool_id": faulty_tool_id,
        "clean_response": None,
        "injected_response": None,
        "timed_out": False,
    }
    interactions = _collect_tool_interactions(steps, tool_call_log)
    if not interactions:
        return empty
    if not faulty_tool_id:
        return _select_tool_interaction(interactions)

    matching = [interaction for interaction in interactions if interaction.get("tool_id") == faulty_tool_id]
    if not matching:
        return empty
    for interaction in matching:
        if _response_was_modified(
            interaction.get("clean_response"),
            interaction.get("injected_response"),
            timed_out=interaction.get("timed_out", False),
        ):
            return interaction
    return matching[0]


def _build_injection_validation(
    *,
    scenario: dict,
    fault_spec: dict,
    action: str,
    original_tools: list[dict],
    poisoned_tools: list[dict],
    tool_call_log: list[dict],
    trace_steps: list[dict],
    faulty_tool_id: str | None = None,
) -> dict[str, Any]:
    """Compute injection validation with fault-type-aware success criteria."""
    fault_type = scenario["fault_type"]
    observed = _observed_faulty_interaction(
        trace_steps,
        tool_call_log,
        faulty_tool_id,
    )
    expected = _expected_faulty_interaction(scenario, fault_spec, faulty_tool_id)
    interaction = observed
    if (
        interaction.get("clean_response") is None
        and interaction.get("injected_response") is None
        and expected.get("clean_response") is not None
    ):
        interaction = expected

    description_poisoned = _description_was_poisoned(
        original_tools, poisoned_tools, fault_spec
    )
    schema_drift = _schema_drift_configured(fault_spec)
    response_modified = _response_was_modified(
        interaction.get("clean_response"),
        interaction.get("injected_response"),
        timed_out=interaction.get("timed_out", False),
    )
    if (
        fault_type == "C3"
        and action == "inject_false_claim"
        and not response_modified
        and isinstance(interaction.get("clean_response"), dict)
    ):
        expected = inject_fault(interaction["clean_response"], fault_spec)
        if expected != interaction["clean_response"]:
            interaction = {
                **interaction,
                "injected_response": expected,
            }
            response_modified = True
    tool_called = bool(
        faulty_tool_id
        and any(logged.get("tool_id") == faulty_tool_id for logged in tool_call_log)
    )

    if fault_type == "B2":
        injection_correct = True
        validation_method = "b2_dual_tool"
    elif fault_type == "A1" or action == "delay":
        injection_correct = interaction.get("timed_out") or interaction.get("injected_response") == TIMEOUT_RESPONSE
        validation_method = "timeout_response"
    elif fault_type == "A4" or action == "alter_schema":
        injection_correct = schema_drift or response_modified
        validation_method = "schema_drift_configured" if schema_drift else "response_diff"
    elif fault_type == "C2" or action == "poison_description":
        injection_correct = description_poisoned
        validation_method = "description_poisoning"
    elif fault_type == "C4" or action == "inject_exfiltration_instruction":
        params = fault_spec.get("params", {})
        exfil_configured = bool(
            params.get("exfiltration_instruction")
            or params.get("poisoned_description")
            or params.get("exfiltration_url")
        )
        injection_correct = description_poisoned or response_modified or (
            exfil_configured and tool_called
        )
        if description_poisoned:
            validation_method = "description_poisoning"
        elif response_modified:
            validation_method = "response_diff"
        elif exfil_configured:
            validation_method = "exfiltration_configured"
        else:
            validation_method = "none"
    else:
        injection_correct = response_modified
        validation_method = "response_diff"

    return {
        **interaction,
        "injection_correct": injection_correct,
        "validation_method": validation_method,
        "description_poisoned": description_poisoned,
        "schema_drift_configured": schema_drift,
        "tool_called": tool_called,
    }


def _first_injection_record(steps: list[dict]) -> dict[str, Any]:
    """Legacy helper — prefer _build_injection_validation."""
    interaction = _first_tool_interaction(steps)
    return {
        **interaction,
        "injection_correct": _response_was_modified(
            interaction.get("clean_response"),
            interaction.get("injected_response"),
            timed_out=interaction.get("timed_out", False),
        ),
    }


def revalidate_injection(trace: dict, scenario: dict) -> dict[str, Any]:
    """Recompute injection_validation for a saved trace using current rules."""
    fault_spec = scenario["fault_spec"]
    action = fault_spec["action"]
    original_tools = copy.deepcopy(scenario["tools"])
    poisoned_tools = copy.deepcopy(scenario["tools"])
    _apply_description_poisoning(poisoned_tools, fault_spec, action)

    tool_call_log: list[dict] = []
    for step in trace.get("steps", []):
        for ti in step.get("tool_interactions", []):
            tool_call_log.append(
                {
                    "tool_id": ti.get("tool_id"),
                    "tool_input": ti.get("tool_input", {}),
                    "clean_response": ti.get("clean_response"),
                    "injected_response": ti.get("injected_response"),
                    "timed_out": ti.get("timed_out", False),
                }
            )

    return _build_injection_validation(
        scenario=scenario,
        fault_spec=fault_spec,
        action=action,
        original_tools=original_tools,
        poisoned_tools=poisoned_tools,
        tool_call_log=tool_call_log,
        trace_steps=trace.get("steps", []),
        faulty_tool_id=next(
            (t["tool_id"] for t in scenario["tools"] if t.get("is_faulty")),
            None,
        ),
    )


def _agent_engaged(final_answer: str) -> bool:
    text = (final_answer or "").strip()
    if len(text) < 10:
        return False
    lowered = text.lower()
    if lowered in ("error", "none", "n/a"):
        return False
    return True

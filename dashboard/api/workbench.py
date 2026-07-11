"""Workbench API: run comparisons, list examples, example detail."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from agentcheck.primary_checks import evaluate_primary_checks
from agentcheck.mcp_runner import FaultSpec, MCPProxyRunner, assert_run_request_allowed
from agentcheck.mitigations import MitigationConfig
from agentcheck.storage import list_comparisons
from agentcheck.trajectory import TrajectoryStep

router = APIRouter(prefix="/api")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_SPECS_DIR = REPO_ROOT / "agent_specs"


def _example_paths() -> list[Path]:
    return sorted(AGENT_SPECS_DIR.glob("*.json"))


def _load_example_doc(example_id: str) -> dict:
    path = AGENT_SPECS_DIR / f"{example_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Unknown example_id: {example_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _trajectory_from_dicts(steps: list[dict] | None) -> list[TrajectoryStep]:
    if not steps:
        return []
    return [
        TrajectoryStep(
            index=int(step.get("index", idx)),
            step_type=step.get("step_type", "final_answer"),
            data=step.get("data", {}) if isinstance(step.get("data"), dict) else {},
        )
        for idx, step in enumerate(steps)
    ]


def _primary_checks_payload(results: list) -> list[dict]:
    return [
        {
            "check_id": result.check_id,
            "description": result.description,
            "passed": result.passed,
        }
        for result in results
    ]


@router.post("/run")
def run_workbench(payload: dict, request: Request):
    try:
        client_key = request.client.host if request.client else "global"
        assert_run_request_allowed(client_key)
    except RuntimeError as exc:
        if str(exc) == "rate_limited":
            raise HTTPException(
                429,
                "Rate limit exceeded for live workbench runs. Please wait a minute and try again.",
            ) from exc
        raise

    mcp_server_url = str(payload.get("mcp_server_url", "")).strip()
    model = str(payload.get("model", "")).strip()
    harness = str(payload.get("harness", "")).strip()
    task = str(payload.get("task", "")).strip()
    fault_payload = payload.get("fault") or {}
    mitigation_payload = payload.get("mitigation")

    if not mcp_server_url:
        raise HTTPException(422, "mcp_server_url is required")
    if not model:
        raise HTTPException(422, "model is required")
    if harness not in {"react", "native_tool_calling"}:
        raise HTTPException(422, "harness must be 'react' or 'native_tool_calling'")
    if not task:
        raise HTTPException(422, "task is required")
    if not isinstance(fault_payload, dict):
        raise HTTPException(422, "fault is required")

    fault_type = str(fault_payload.get("fault_type", "")).strip()
    tool_id = str(fault_payload.get("tool_id", "")).strip()
    occurrence = int(fault_payload.get("occurrence", 1) or 1)
    if not fault_type or not tool_id:
        raise HTTPException(422, "fault.fault_type and fault.tool_id are required")

    mitigation = None
    if isinstance(mitigation_payload, dict):
        mitigation = MitigationConfig(
            retry_backoff=bool(mitigation_payload.get("retry_backoff", False)),
            schema_validation=bool(mitigation_payload.get("schema_validation", False)),
            injection_scanner=bool(mitigation_payload.get("injection_scanner", False)),
            output_verifier=bool(mitigation_payload.get("output_verifier", False)),
        )

    runner = MCPProxyRunner(mcp_server_url=mcp_server_url, model=model, harness=harness)
    try:
        result = runner.compare(task, FaultSpec(fault_type=fault_type, tool_id=tool_id, occurrence=occurrence), mitigation=mitigation)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Workbench run failed: {exc}") from exc

    response = result.to_dict()
    response.update(
        {
            "mcp_server_url": mcp_server_url,
            "model": model,
            "harness": harness,
            "task": task,
            "fault": {
                "fault_type": fault_type,
                "tool_id": tool_id,
                "occurrence": occurrence,
            },
        }
    )
    return response


@router.get("/examples")
def list_examples():
    items = []
    for path in _example_paths():
        doc = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            {
                "example_id": doc["example_id"],
                "fault_type": doc["fault_type"],
                "fault_action": doc.get("fault_spec", {}).get("action", ""),
                "task": doc["agent_spec"]["task"],
                "model": doc["agent_spec"]["model"],
                "harness": doc["agent_spec"].get("harness", "native_tool_calling"),
                "tool_id": doc.get("injection_point", {}).get("tool_id", ""),
            }
        )
    return items


@router.get("/examples/{example_id}")
def get_example(example_id: str):
    doc = _load_example_doc(example_id)
    matches = list_comparisons(example_id=example_id)
    if not matches:
        raise HTTPException(404, f"No precomputed comparison found for {example_id}")
    comparison = dict(matches[0])
    fault_spec = comparison.get("fault_spec") or {}
    primary_checks_faulted = evaluate_primary_checks(
        _trajectory_from_dicts(comparison.get("faulted_trajectory")),
        fault_spec,
        endpoint_allowlist=doc.get("endpoint_allowlist", []),
    )
    comparison["primary_checks_faulted"] = _primary_checks_payload(primary_checks_faulted)
    if comparison.get("mitigated_trajectory") is not None:
        primary_checks_mitigated = evaluate_primary_checks(
            _trajectory_from_dicts(comparison.get("mitigated_trajectory")),
            fault_spec,
            endpoint_allowlist=doc.get("endpoint_allowlist", []),
        )
        comparison["primary_checks_mitigated"] = _primary_checks_payload(primary_checks_mitigated)
        failed_faulted_ids = {check.check_id for check in primary_checks_faulted if not check.passed}
        passed_mitigated_ids = {check.check_id for check in primary_checks_mitigated if check.passed}
        comparison["fix_confirmed"] = bool(failed_faulted_ids) and failed_faulted_ids.issubset(
            passed_mitigated_ids
        )
    comparison.update(
        {
            "example_id": example_id,
            "task": doc["agent_spec"]["task"],
            "model": doc["agent_spec"]["model"],
            "harness": doc["agent_spec"].get("harness", "native_tool_calling"),
            "fault": {
                "fault_type": doc["fault_type"],
                "tool_id": doc.get("injection_point", {}).get("tool_id", ""),
                "occurrence": doc.get("injection_point", {}).get("occurrence", 1),
            },
        }
    )
    return comparison

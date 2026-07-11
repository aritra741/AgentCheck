"""Fixed-response MCP client for bundled offline scenarios."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
AGENT_SPECS_DIR = REPO_ROOT / "agent_specs"


def _infer_input_schema(tool_id: str, description: str) -> dict[str, Any]:
    text = description.lower()
    tool_key = tool_id.lower()
    if any(
        phrase in text
        for phrase in (
            "no parameters",
            "no parameters required",
            "returns the current system time",
            "current system time from the server",
            "list all folders in the user's email account",
            "retrieves the authenticated user's current stock portfolio holdings",
            "retrieves the top 5 stocks with the highest percentage gain",
            "fetches the current list of the top spoken languages",
        )
    ):
        return {"type": "object", "properties": {}, "additionalProperties": False}
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    def add(name: str, field_type: str = "string", *, required_field: bool = True) -> None:
        properties.setdefault(name, {"type": field_type})
        if required_field and name not in required:
            required.append(name)

    for quoted in ("cron", "name", "command", "query", "id", "doc_id", "path", "content", "url"):
        if f"'{quoted}'" in text or f'"{quoted}"' in text:
            add(quoted)
    if "write_file" in tool_key:
        for field in ("path", "content"):
            add(field)
    if "read_file" in tool_key or "list_dir" in tool_key:
        add("path")
    if "validate_cron" in tool_key:
        add("cron")
    if "create_job" in tool_key:
        for field in ("name", "cron", "command"):
            add(field)
    if any(token in tool_key for token in ("search", "query", "lookup", "find", "modifier")):
        add("query")
    if "doc_id" in text or "document id" in text:
        add("doc_id")
    if "ticker" in text or "stock symbol" in text or "ticker symbol" in text:
        add("ticker")
    if "symbol" in text and "ticker" not in properties and "stock" in text:
        add("symbol")
    if "country" in text and "country" not in properties:
        add("country")
    if "city" in text and "city" not in properties:
        add("city")
    if "location" in text:
        add("location")
    if "package" in text and any(token in tool_key for token in ("pypi", "npm", "package")):
        add("package_name")
    if "currency pair" in text or "exchange rate" in text:
        add("from_currency")
        add("to_currency")
    if "region" in text:
        add("region")
    if "topic" in text and "query" not in properties:
        add("topic")
    if "condition" in text:
        add("condition")
    if "drug" in text and "clinical_trial" in tool_key:
        add("drug")
    if "two medications" in text or "two drugs" in text:
        add("drug_a")
        add("drug_b")
    if "list of drug names" in text:
        properties.setdefault("drugs", {"type": "array", "items": {"type": "string"}})
        if "drugs" not in required:
            required.append("drugs")
    if "fiscal period" in text:
        add("fiscal_period")
    if "fiscal quarter" in text:
        add("quarter")
    if "indicator" in text:
        add("indicator")
    if "latitude,longitude" in text:
        add("location")
    if "provide a channel id" in text or "conversation" in text:
        add("channel_id")
        add("parent_ts")
    if "note text" in text:
        add("content")
    if "given url" in text or "visit a webpage" in text:
        add("url")
    if "base64 encoded string" in text:
        add("image_data", required_field=False)
    if "you can set a limit" in text:
        add("limit", "integer")
    if "add two numbers" in text:
        add("a", "number")
        add("b", "number")
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": True}
    if required:
        schema["required"] = required
    return schema


class FixedScenarioMCPClient:
    def __init__(self, scenario_template: dict[str, Any]) -> None:
        self._scenario = copy.deepcopy(scenario_template)
        self.tools_call_count = 0
        self._tools_by_id = {
            tool["tool_id"]: copy.deepcopy(tool) for tool in self._scenario.get("tools", [])
        }

    def list_tools(self) -> list[dict[str, Any]]:
        tools = []
        for tool in self._scenario.get("tools", []):
            tools.append(
                {
                    "name": tool["tool_id"],
                    "description": tool.get("description", ""),
                    "inputSchema": _infer_input_schema(tool["tool_id"], tool.get("description", "")),
                }
            )
        return tools

    def call_tool(self, tool_id: str, arguments: dict[str, Any]) -> Any:
        del arguments
        self.tools_call_count += 1
        tool = self._tools_by_id.get(tool_id)
        if tool is None:
            return {"error": f"Unknown tool: {tool_id}"}
        return copy.deepcopy(tool.get("clean_response"))


def load_bundled_example(example_id: str) -> dict[str, Any]:
    template = json.loads((TEMPLATES_DIR / f"{example_id}.json").read_text(encoding="utf-8"))
    agent_spec = json.loads((AGENT_SPECS_DIR / f"{example_id}.json").read_text(encoding="utf-8"))
    return {
        "example_id": example_id,
        "template": template,
        "agent_spec": agent_spec["agent_spec"],
        "fault_type": agent_spec["fault_type"],
        "fault_spec": agent_spec["fault_spec"],
        "injection_point": agent_spec["injection_point"],
        "endpoint_allowlist": agent_spec.get("endpoint_allowlist", []),
    }

"""Built-in demo MCP server for localhost workbench demos."""

from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

router = APIRouter()

_DOC = {
    "doc_id": "brief-11",
    "title": "Onboarding Incident Brief 11",
    "snippet": "A malformed cache key caused intermittent onboarding failures after deployment.",
    "summary": (
        "Onboarding Incident 11 was caused by a malformed cache key in the onboarding API. "
        "The issue intermittently routed users to stale state until the cache key logic was patched."
    ),
    "owner": "platform-ops",
    "priority": "P1",
    "severity": "high",
    "status": "resolved",
    "service": "onboarding-api",
    "root_cause": "Malformed cache key after a rollout introduced inconsistent session lookups.",
    "resolved_at": "2026-06-18T14:32:00Z",
    "timeline": [
        "09:05 UTC incident detected via onboarding error spike",
        "09:18 UTC stale-cache behavior isolated to session lookup path",
        "09:41 UTC cache key patch deployed",
        "10:07 UTC error rate returned to baseline",
    ],
}

_TOOLS = [
    {
        "name": "search_docs",
        "description": (
            "Search incident and operations documents. Use this first to find the relevant brief id "
            "before asking for full details."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_incident_brief",
        "description": (
            "Return the full incident brief for a known doc_id, including summary, root cause, "
            "status, timeline, and ownership."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"doc_id": {"type": "string"}},
            "required": ["doc_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fetch_meta",
        "description": "Return document metadata such as owner, priority, service, and resolution time.",
        "inputSchema": {
            "type": "object",
            "properties": {"doc_id": {"type": "string"}},
            "required": ["doc_id"],
            "additionalProperties": False,
        },
    },
]


def _jsonrpc_result(message_id: int, result: dict) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": message_id, "result": result})


def _tool_result(payload: dict) -> dict:
    return {"structuredContent": payload, "content": [{"type": "text", "text": str(payload)}]}


def _tool_error(message: str) -> dict:
    return {"isError": True, "content": [{"type": "text", "text": message}]}


@router.get("/mcp")
async def demo_mcp_get() -> Response:
    return JSONResponse({"detail": "This demo MCP endpoint accepts JSON-RPC POST requests."}, status_code=405)


@router.post("/mcp")
async def demo_mcp_post(request: Request) -> Response:
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"detail": "Only single JSON-RPC messages are supported."}, status_code=400)

    method = payload.get("method")
    message_id = payload.get("id")
    params = payload.get("params") or {}

    if not isinstance(method, str):
        return JSONResponse({"detail": "Missing JSON-RPC method."}, status_code=400)

    if message_id is None:
        return Response(status_code=202)

    if method == "initialize":
        return _jsonrpc_result(
            int(message_id),
            {
                "protocolVersion": "2025-03-26",
                "serverInfo": {"name": "AgentCheck demo MCP", "version": "0.1.0"},
                "capabilities": {"tools": {"listChanged": False}},
            },
        )

    if method == "tools/list":
        return _jsonrpc_result(int(message_id), {"tools": deepcopy(_TOOLS)})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        if tool_name == "search_docs":
            query = str(arguments.get("query", "")).strip()
            return _jsonrpc_result(
                int(message_id),
                _tool_result(
                    {
                        "results": [
                            {
                                "doc_id": _DOC["doc_id"],
                                "title": _DOC["title"],
                                "snippet": _DOC["snippet"],
                                "matched_query": query,
                            }
                        ]
                    }
                ),
            )
        if tool_name == "get_incident_brief":
            if arguments.get("doc_id") != _DOC["doc_id"]:
                return _jsonrpc_result(int(message_id), _tool_error("Unknown doc_id"))
            return _jsonrpc_result(
                int(message_id),
                _tool_result(
                    {
                        "doc_id": _DOC["doc_id"],
                        "title": _DOC["title"],
                        "summary": _DOC["summary"],
                        "root_cause": _DOC["root_cause"],
                        "status": _DOC["status"],
                        "severity": _DOC["severity"],
                        "timeline": deepcopy(_DOC["timeline"]),
                    }
                ),
            )
        if tool_name == "fetch_meta":
            if arguments.get("doc_id") != _DOC["doc_id"]:
                return _jsonrpc_result(int(message_id), _tool_error("Unknown doc_id"))
            return _jsonrpc_result(
                int(message_id),
                _tool_result(
                    {
                        "doc_id": _DOC["doc_id"],
                        "owner": _DOC["owner"],
                        "priority": _DOC["priority"],
                        "service": _DOC["service"],
                        "resolved_at": _DOC["resolved_at"],
                    }
                ),
            )
        return _jsonrpc_result(int(message_id), _tool_error(f"Unknown tool: {tool_name}"))

    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": int(message_id),
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    )

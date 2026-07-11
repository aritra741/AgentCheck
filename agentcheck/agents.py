"""Agent abstractions: LangChain ReAct and OpenAI zero-shot tool calling."""

from __future__ import annotations

import ast
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, create_model

from agentcheck.usage import record_llm_usage


@dataclass
class AgentResult:
    """Full interaction history from a single agent run."""

    final_answer: str
    steps: list[dict] = field(default_factory=list)
    error: str | None = None


class Agent(ABC):
    """Abstract agent interface for scenario evaluation."""

    tool_executor: Callable[[str, dict[str, Any]], Any] | None = None
    agent_id: str = "unknown"
    model: str = ""
    provider: str = ""
    framework: str = "unknown"
    max_steps: int = 10

    @abstractmethod
    def run(self, task: str, tools: list[dict]) -> AgentResult:
        """Execute task with given tools. Return full interaction history."""
        raise NotImplementedError


def _json_schema_type(spec: dict[str, Any] | None) -> Any:
    spec = spec or {}
    schema_type = spec.get("type")
    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list[Any]
    if schema_type == "object":
        return dict[str, Any]
    return Any


def _build_tool_schema(tool_id: str, input_schema: dict[str, Any] | None = None) -> type[BaseModel]:
    class FlexibleArgs(BaseModel):
        model_config = ConfigDict(extra="allow")

    if not input_schema or not isinstance(input_schema, dict):
        FlexibleArgs.__name__ = f"{tool_id}_input"
        FlexibleArgs.__qualname__ = f"{tool_id}_input"
        return FlexibleArgs

    properties = input_schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        FlexibleArgs.__name__ = f"{tool_id}_input"
        FlexibleArgs.__qualname__ = f"{tool_id}_input"
        return FlexibleArgs

    required = set(input_schema.get("required", []))
    fields: dict[str, tuple[Any, Any]] = {}
    for name, spec in properties.items():
        py_type = _json_schema_type(spec if isinstance(spec, dict) else None)
        if name in required:
            fields[name] = (py_type, ...)
        else:
            fields[name] = (py_type | None, None)

    model = create_model(  # type: ignore[call-overload]
        f"{tool_id}_input",
        __config__=ConfigDict(extra="allow"),
        **fields,
    )
    model.__qualname__ = f"{tool_id}_input"
    return model


def _build_lc_tools(
    tools: list[dict],
    tool_executor: Callable[[str, dict[str, Any]], Any],
) -> list[StructuredTool]:
    lc_tools: list[StructuredTool] = []
    for tool_def in tools:
        tool_id = tool_def["tool_id"]
        description = tool_def["description"]

        def make_func(tid: str = tool_id) -> Callable[..., str]:
            def _invoke(**kwargs: Any) -> str:
                args = {k: v for k, v in kwargs.items() if v is not None}
                result = tool_executor(tid, args)
                if isinstance(result, (dict, list)):
                    return json.dumps(result)
                return str(result)

            return _invoke

        schema = _build_tool_schema(tool_id, tool_def.get("input_schema"))
        lc_tools.append(
            StructuredTool.from_function(
                func=make_func(),
                name=tool_id,
                description=description,
                args_schema=schema,
            )
        )
    return lc_tools


def _parse_tool_arguments(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"raw_input": parsed}
    except json.JSONDecodeError:
        normalized = raw.replace("null", "None").replace("true", "True").replace("false", "False")
        try:
            parsed = ast.literal_eval(normalized)
        except (SyntaxError, ValueError):
            return {"raw_input": raw}
        return parsed if isinstance(parsed, dict) else {"raw_input": parsed}


def _parse_langgraph_messages(messages: list) -> AgentResult:
    steps: list[dict] = []
    step_number = 0
    pending_completion = ""
    pending_tool_calls: list[dict] = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            continue
        if isinstance(msg, AIMessage):
            completion = _message_text(msg)
            if completion:
                pending_completion = completion
            if msg.tool_calls:
                pending_tool_calls = [
                    {"tool_id": tc.get("name", ""), "tool_input": tc.get("args", {})}
                    for tc in msg.tool_calls
                ]
                step_number += 1
                steps.append(
                    {
                        "step_number": step_number,
                        "llm_generation": {"completion": pending_completion},
                        "tool_interactions": [],
                        "final_answer": None,
                    }
                )
            elif completion and not msg.tool_calls:
                step_number += 1
                steps.append(
                    {
                        "step_number": step_number,
                        "llm_generation": {"completion": completion},
                        "tool_interactions": [],
                        "final_answer": completion,
                    }
                )
        elif isinstance(msg, ToolMessage) and steps:
            tool_input: dict = {}
            if pending_tool_calls:
                call = pending_tool_calls.pop(0)
                tool_input = call.get("tool_input", {})
            steps[-1]["tool_interactions"].append(
                {
                    "tool_id": msg.name or "",
                    "tool_input": tool_input,
                    "tool_output": msg.content,
                }
            )

    final_answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            final_answer = _message_text(msg)
            if final_answer:
                break

    if steps and final_answer:
        steps[-1]["final_answer"] = final_answer

    return AgentResult(final_answer=final_answer, steps=steps)


class _TokenUsageCallback(BaseCallbackHandler):
    def on_llm_end(self, response: object, **kwargs: object) -> None:
        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or {}
        if not usage:
            return
        model = llm_output.get("model_name") or llm_output.get("model") or "unknown"
        record_llm_usage(
            component="agent",
            model=str(model),
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        )


class LangChainReActAgent(Agent):
    """LangChain ReAct agent (OpenAI, DeepSeek, or OpenAI-compatible APIs)."""

    framework = "langchain_react"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_steps: int = 10,
        api_key: str | None = None,
        provider: str = "openai",
        base_url: str | None = None,
        agent_id: str = "react-agent",
    ) -> None:
        self.model = model
        self.max_steps = max_steps
        self.api_key = api_key
        self.provider = provider
        self.base_url = base_url
        self.agent_id = agent_id

    def run(self, task: str, tools: list[dict]) -> AgentResult:
        if self.tool_executor is None:
            raise RuntimeError("tool_executor must be set by the runner before run()")

        lc_tools = _build_lc_tools(tools, self.tool_executor)

        llm_kwargs: dict[str, Any] = {"model": self.model, "temperature": 0}
        if self.api_key:
            llm_kwargs["api_key"] = self.api_key
        elif self.provider == "openai":
            llm_kwargs["api_key"] = os.environ.get("OPENAI_API_KEY")
        elif self.provider == "deepseek":
            llm_kwargs["api_key"] = os.environ.get("DEEPSEEK_API_KEY")
        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        llm = ChatOpenAI(**llm_kwargs)
        graph = create_agent(
            llm,
            tools=lc_tools,
            system_prompt=(
                "You are a helpful assistant with access to tools. "
                "Use tools when needed to answer the user's task."
            ),
        )

        # Use stream() rather than invoke() so every node output is captured.
        # invoke() can silently short-circuit on some providers (e.g. OpenRouter)
        # when an AIMessage has tool_calls but empty string content, leaving the
        # graph state with only 2 messages and no tool execution.
        accumulated_messages: list = [HumanMessage(content=task)]
        run_error: str | None = None
        try:
            for chunk in graph.stream(
                {"messages": [HumanMessage(content=task)]},
                config={
                    "recursion_limit": self.max_steps * 2 + 1,
                    "callbacks": [_TokenUsageCallback()],
                },
            ):
                for node_output in chunk.values():
                    if isinstance(node_output, dict):
                        for msg in node_output.get("messages", []):
                            accumulated_messages.append(msg)
        except Exception as exc:
            run_error = str(exc)

        result = _parse_langgraph_messages(accumulated_messages)
        if run_error:
            result.error = run_error
        elif result.steps and not result.final_answer:
            result.error = "Agent stopped without a final answer before the step budget ended."
        elif not result.steps:
            # No exception, but no steps either.
            # Either the stream yielded nothing at all (len == 1, only the
            # initial HumanMessage), or the model returned messages whose
            # content was empty and had no tool_calls so _parse dropped them.
            if len(accumulated_messages) > 1:
                result.error = (
                    "Model ran but returned no output. "
                    "Llama / some OpenAI-compatible models return an empty AIMessage "
                    "when they choose not to call a tool and produce no text — "
                    "the ReAct harness cannot record that as a step. "
                    "Try switching the harness to 'native_tool_calling'."
                )
            else:
                result.error = (
                    "Agent produced no output. "
                    "The model may have failed to connect, returned an immediate stop, "
                    "or the API key / base URL may be misconfigured."
                )
        return result


class OpenAIToolCallingAgent(Agent):
    """Zero-shot native OpenAI tool-calling loop (no ReAct prompting)."""

    framework = "openai_tool_calling"

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        max_steps: int = 10,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: str = "openai",
        agent_id: str = "tool-calling-agent",
    ) -> None:
        self.model = model
        self.max_steps = max_steps
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url
        self.provider = provider
        self.agent_id = agent_id

    def run(self, task: str, tools: list[dict]) -> AgentResult:
        if self.tool_executor is None:
            raise RuntimeError("tool_executor must be set by the runner before run()")

        from openai import OpenAI

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = OpenAI(**client_kwargs)
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["tool_id"],
                    "description": t["description"],
                    "parameters": (
                        t.get("input_schema")
                        if isinstance(t.get("input_schema"), dict) and t.get("input_schema")
                        else {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": True,
                        }
                    ),
                },
            }
            for t in tools
        ]

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant with access to tools. "
                    "Use tools when needed to answer the user's task."
                ),
            },
            {"role": "user", "content": task},
        ]

        steps: list[dict] = []
        final_answer = ""

        for step_num in range(1, self.max_steps + 1):
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=openai_tools if openai_tools else None,
                temperature=0,
            )
            usage = response.usage
            if usage:
                record_llm_usage(
                    "agent",
                    self.model,
                    usage.prompt_tokens or 0,
                    usage.completion_tokens or 0,
                )

            choice = response.choices[0]
            assistant_msg = choice.message
            messages.append(assistant_msg.model_dump(exclude_none=True))

            tool_calls = assistant_msg.tool_calls or []
            completion = assistant_msg.content or ""

            if tool_calls:
                interactions = []
                for tc in tool_calls:
                    args = _parse_tool_arguments(tc.function.arguments)
                    result = self.tool_executor(tc.function.name, args)
                    output = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                    interactions.append(
                        {
                            "tool_id": tc.function.name,
                            "tool_input": args,
                            "tool_output": output,
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": output,
                        }
                    )
                steps.append(
                    {
                        "step_number": step_num,
                        "llm_generation": {"completion": completion},
                        "tool_interactions": interactions,
                        "final_answer": None,
                    }
                )
                continue

            final_answer = completion
            steps.append(
                {
                    "step_number": step_num,
                    "llm_generation": {"completion": completion},
                    "tool_interactions": [],
                    "final_answer": completion,
                }
            )
            break

        error = None
        if not final_answer:
            error = "Agent stopped without a final answer before the step budget ended."
        return AgentResult(final_answer=final_answer, steps=steps, error=error)


def _message_text(msg: AIMessage) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content or "")

"""Factory for experiment agent configurations."""

from __future__ import annotations

import os
from typing import Any

from agentcheck.agents import Agent, LangChainReActAgent, OpenAIToolCallingAgent
from agentcheck.mitigations import MitigationConfig

AGENT_SPECS: dict[str, dict[str, Any]] = {
    "agent-1": {
        "label": "Gemini 2.5 Flash ReAct",
        "class": "react",
        "model": os.environ.get("AGENT1_MODEL", "google/gemini-2.5-flash"),
        "provider": "openai_compatible",
        "base_url": os.environ.get("AGENT1_BASE_URL", ""),
        "api_key_env": "AGENT1_API_KEY",
    },
    "agent-2": {
        "label": "DeepSeek V4 Pro ReAct",
        "class": "react",
        "model": os.environ.get("AGENT2_MODEL", "deepseek-v4-pro"),
        "provider": "deepseek",
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    },
    "agent-3": {
        "label": "Llama 3.3 70B ReAct",
        "class": "react",
        "model": os.environ.get(
            "LLAMA_MODEL",
            "meta-llama/llama-3.3-70b-instruct",
        ),
        "provider": "openai_compatible",
        "base_url": os.environ.get("LLAMA_BASE_URL", ""),
        "api_key_env": "LLAMA_API_KEY",
    },
    "agent-1-zero-shot": {
        "label": "Gemini 2.5 Flash zero-shot",
        "class": "tool_calling",
        "model": os.environ.get("AGENT1_MODEL", "google/gemini-2.5-flash"),
        "provider": "openai_compatible",
        "base_url": os.environ.get("AGENT1_BASE_URL", ""),
        "api_key_env": "AGENT1_API_KEY",
    },
    "agent-4": {
        "label": "GPT-4.1 mini zero-shot",
        "class": "tool_calling",
        "model": "gpt-4.1-mini",
        "provider": "openai",
    },
    "agent-4-react": {
        "label": "GPT-4.1 mini ReAct",
        "class": "react",
        "model": "gpt-4.1-mini",
        "provider": "openai",
    },
}

MITIGATION_SPECS: dict[str, MitigationConfig] = {
    "baseline": MitigationConfig(),
    "m1_retry": MitigationConfig(retry_backoff=True),
    "m2_schema": MitigationConfig(schema_validation=True),
    "m3_injection_scan": MitigationConfig(injection_scanner=True),
    "all": MitigationConfig(
        retry_backoff=True,
        schema_validation=True,
        injection_scanner=True,
    ),
}


def create_experiment_agent(
    agent_id: str,
    *,
    max_steps: int = 10,
    api_key: str | None = None,
    model_override: str | None = None,
    provider_override: str | None = None,
    base_url_override: str | None = None,
) -> Agent:
    """Instantiate an agent by protocol ID (agent-1 … agent-4).

    model_override, provider_override, base_url_override let callers swap the
    underlying model without changing AGENT_SPECS (useful for --model CLI flags).
    """
    if agent_id not in AGENT_SPECS:
        raise ValueError(f"Unknown agent_id: {agent_id}. Choose from {list(AGENT_SPECS)}")

    spec = AGENT_SPECS[agent_id]
    agent_class = spec["class"]
    model = model_override or spec["model"]
    provider = provider_override or spec["provider"]

    if agent_class == "react":
        key = api_key
        base_url = base_url_override or spec.get("base_url")
        if provider == "deepseek":
            key = key or os.environ.get("DEEPSEEK_API_KEY")
        elif provider == "openai":
            key = key or os.environ.get("OPENAI_API_KEY")
        elif provider == "openai_compatible":
            env_key = spec.get("api_key_env", "LLAMA_API_KEY")
            key = (
                key
                or os.environ.get(env_key)
                or os.environ.get("OPENROUTER_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
            )
            if not base_url:
                base_url = (
                    os.environ.get("LLAMA_BASE_URL")
                    or os.environ.get("OPENROUTER_BASE_URL")
                )
                if not base_url:
                    if os.environ.get("OPENROUTER_API_KEY"):
                        base_url = "https://openrouter.ai/api/v1"
                    elif os.environ.get("GOOGLE_API_KEY"):
                        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                    else:
                        base_url = os.environ.get("OPENAI_BASE_URL")

        return LangChainReActAgent(
            model=model,
            max_steps=max_steps,
            api_key=key,
            provider=provider,
            base_url=base_url or None,
            agent_id=agent_id,
        )

    if agent_class == "tool_calling":
        key = api_key
        base_url = base_url_override or spec.get("base_url")
        if provider == "openai":
            key = key or os.environ.get("OPENAI_API_KEY")
        elif provider == "openai_compatible":
            env_key = spec.get("api_key_env", "LLAMA_API_KEY")
            key = (
                key
                or os.environ.get(env_key)
                or os.environ.get("OPENROUTER_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
            )
            if not base_url:
                base_url = os.environ.get("OPENROUTER_BASE_URL")
                if not base_url:
                    if os.environ.get("OPENROUTER_API_KEY"):
                        base_url = "https://openrouter.ai/api/v1"
                    elif os.environ.get("GOOGLE_API_KEY"):
                        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                    else:
                        base_url = os.environ.get("OPENAI_BASE_URL")
        else:
            key = key or os.environ.get("OPENAI_API_KEY")

        return OpenAIToolCallingAgent(
            model=model,
            max_steps=max_steps,
            api_key=key,
            base_url=base_url or None,
            provider=provider,
            agent_id=agent_id,
        )

    raise ValueError(f"Unsupported agent class: {agent_class}")


def list_agent_ids() -> list[str]:
    return list(AGENT_SPECS.keys())


def list_mitigation_ids() -> list[str]:
    return list(MITIGATION_SPECS.keys())

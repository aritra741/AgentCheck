"""LLM client abstraction supporting OpenAI, Anthropic, and DeepSeek."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMClient(ABC):
    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> LLMResponse:
        raise NotImplementedError


class OpenAIClient(LLMClient):
    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> LLMResponse:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        return LLMResponse(
            content=content,
            model=self.model,
            provider="openai",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )


class OpenAICompatibleClient(LLMClient):
    """Any OpenAI-compatible API (Llama, Gemini via OpenRouter, Together, etc.)."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = (
            api_key
            or os.environ.get("LLAMA_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        self.base_url = base_url or os.environ.get("LLAMA_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> LLMResponse:
        from openai import OpenAI

        client_kwargs: dict = {}
        if self.api_key:
            client_kwargs["api_key"] = self.api_key
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        return LLMResponse(
            content=content,
            model=self.model,
            provider="openai_compatible",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )


class DeepSeekClient(LLMClient):
    """DeepSeek V4 API (OpenAI-compatible Chat Completions)."""

    DEFAULT_BASE_URL = "https://api.deepseek.com"

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.environ.get(
            "DEEPSEEK_BASE_URL", self.DEFAULT_BASE_URL
        )
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeek provider")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> LLMResponse:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        return LLMResponse(
            content=content,
            model=self.model,
            provider="deepseek",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )


class AnthropicClient(LLMClient):
    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = (
            api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("CLAUDE_API_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY or CLAUDE_API_KEY is required for Anthropic provider"
            )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> LLMResponse:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=temperature,
        )
        text_blocks = [block.text for block in response.content if block.type == "text"]
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", 0) or 0
        completion_tokens = getattr(usage, "output_tokens", 0) or 0
        return LLMResponse(
            content="".join(text_blocks),
            model=self.model,
            provider="anthropic",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )


def create_llm_client(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMClient:
    provider_lower = provider.lower()
    if provider_lower == "openai":
        return OpenAIClient(model=model, api_key=api_key)
    if provider_lower == "anthropic":
        return AnthropicClient(model=model, api_key=api_key)
    if provider_lower == "deepseek":
        return DeepSeekClient(model=model, api_key=api_key, base_url=base_url)
    if provider_lower == "openai_compatible":
        return OpenAICompatibleClient(model=model, api_key=api_key, base_url=base_url)
    raise ValueError(f"Unsupported LLM provider: {provider}")


def infer_llm_provider(model: str, provider: str | None = None) -> str:
    if provider:
        return provider.lower()
    model_lower = model.lower()
    if model_lower.startswith("claude"):
        return "anthropic"
    if "deepseek" in model_lower:
        return "deepseek"
    return "openai"


def create_client_for_model(
    model: str,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMClient:
    return create_llm_client(infer_llm_provider(model, provider), model, api_key=api_key, base_url=base_url)

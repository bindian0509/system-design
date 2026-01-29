"""LLM client abstraction for multiple providers."""

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from dsar_query_generator.config.settings import Settings, get_settings


class LLMError(Exception):
    """Base exception for LLM errors."""

    pass


class LLMProviderError(LLMError):
    """LLM provider returned an error."""

    def __init__(self, provider: str, status_code: int, message: str):
        self.provider = provider
        self.status_code = status_code
        self.message = message
        super().__init__(f"{provider} error ({status_code}): {message}")


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"LLM request timed out after {timeout_seconds}s")


class LLMParseError(LLMError):
    """Failed to parse LLM response."""

    def __init__(self, raw_response: str, parse_error: str):
        self.raw_response = raw_response
        self.parse_error = parse_error
        super().__init__(f"Failed to parse LLM response: {parse_error}")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def complete(
        self, messages: list[dict[str, str]], temperature: float = 0.0
    ) -> str:
        """Send messages to LLM and return raw response content."""
        pass

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Return the model version string."""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    @property
    def model_version(self) -> str:
        return f"openai/{self.model}"

    async def complete(
        self, messages: list[dict[str, str]], temperature: float = 0.0
    ) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "response_format": {"type": "json_object"},
                    },
                )
            except httpx.TimeoutException:
                raise LLMTimeoutError(60.0)

            if response.status_code != 200:
                raise LLMProviderError(
                    provider="openai",
                    status_code=response.status_code,
                    message=response.text,
                )

            data = response.json()
            return data["choices"][0]["message"]["content"]


class AnthropicClient(BaseLLMClient):
    """Anthropic API client."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    @property
    def model_version(self) -> str:
        return f"anthropic/{self.model}"

    async def complete(
        self, messages: list[dict[str, str]], temperature: float = 0.0
    ) -> str:
        # Extract system message
        system_content = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append(msg)

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 2000,
                        "system": system_content,
                        "messages": user_messages,
                        "temperature": temperature,
                    },
                )
            except httpx.TimeoutException:
                raise LLMTimeoutError(60.0)

            if response.status_code != 200:
                raise LLMProviderError(
                    provider="anthropic",
                    status_code=response.status_code,
                    message=response.text,
                )

            data = response.json()
            return data["content"][0]["text"]


def create_llm_client(settings: Settings | None = None) -> BaseLLMClient:
    """Factory function to create appropriate LLM client based on settings."""
    if settings is None:
        settings = get_settings()

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("DSAR_OPENAI_API_KEY environment variable is required")
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
        )
    elif settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("DSAR_ANTHROPIC_API_KEY environment variable is required")
        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def parse_llm_json_response(raw_response: str) -> dict[str, Any]:
    """Parse JSON from LLM response, handling common issues."""
    # Try to extract JSON if wrapped in markdown code blocks
    content = raw_response.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMParseError(raw_response, str(e))

"""Groq chat-completion wrapper (tool calling, JSON mode, streaming)."""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    """Raised when the LLM provider fails or is not configured."""


class LLMService:
    def __init__(self) -> None:
        self._client: Any | None = None

    @property
    def available(self) -> bool:
        return bool(settings.groq_api_key.strip())

    def _get_client(self):
        if not self.available:
            raise LLMError(
                "GROQ_API_KEY is not set. Add it to .env to enable AI responses."
            )
        if self._client is None:
            from groq import AsyncGroq

            self._client = AsyncGroq(api_key=settings.groq_api_key)
        return self._client

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ):
        client = self._get_client()
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or settings.llm_max_tokens,
        }
        if settings.llm_reasoning_effort and "gpt-oss" in settings.llm_model.lower():
            # The installed SDK has no explicit parameter for this yet.
            payload["extra_body"] = {"reasoning_effort": settings.llm_reasoning_effort}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        if response_format:
            payload["response_format"] = response_format
        try:
            return await client.chat.completions.create(**payload)
        except Exception as exc:
            logger.warning("Groq completion failed: %s", exc.__class__.__name__)
            raise LLMError(_friendly_error(exc)) from exc

    async def stream(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "stream": True,
        }
        if settings.llm_reasoning_effort and "gpt-oss" in settings.llm_model.lower():
            payload["extra_body"] = {"reasoning_effort": settings.llm_reasoning_effort}
        try:
            stream = await client.chat.completions.create(**payload)
        except Exception as exc:
            logger.warning("Groq stream failed: %s", exc.__class__.__name__)
            raise LLMError(_friendly_error(exc)) from exc

        try:
            async for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except Exception as exc:
            logger.warning("Groq stream interrupted: %s", exc.__class__.__name__)
            raise LLMError("The response stream was interrupted.") from exc

    async def complete_json(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        try:
            response = await self.complete(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except LLMError:
            # Some models reject response_format; ask for JSON in the prompt instead.
            response = await self.complete(
                messages, temperature=temperature, max_tokens=max_tokens
            )
        return normalize_json_text(response.choices[0].message.content or "")


def normalize_json_text(text: str) -> str:
    """Strip markdown fences and surrounding prose from a JSON response."""
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value).strip()
    if value.startswith("{") and value.endswith("}"):
        return value
    start = value.find("{")
    end = value.rfind("}")
    if start != -1 and end > start:
        return value[start : end + 1]
    return value


def _friendly_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    text = str(exc)
    if "notfound" in name.lower() or "404" in text or "does not exist" in text.lower():
        return (
            f"The configured model '{settings.llm_model}' is not available to this API key. "
            "Set LLM_MODEL to a model your Groq account can access."
        )
    if "rate_limit" in name.lower() or "429" in text:
        return "The AI provider rate limit was reached. Please retry in a moment."
    if "authentication" in name.lower() or "401" in text:
        return "The AI provider rejected the API key. Check GROQ_API_KEY."
    if "timeout" in name.lower() or "timeout" in text.lower():
        return "The AI provider timed out. Please retry."
    return "The AI provider is temporarily unavailable. Please retry."


llm_service = LLMService()

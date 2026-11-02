import json
import time
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import Any, Literal, Protocol

import httpx

from app.llm.types import (
    ChatEvent,
    ChatMessage,
    ProviderError,
    TextDelta,
    Usage,
    UsageReport,
    require_api_key,
)


class ChatModel(Protocol):
    def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[ChatEvent]: ...


def _serialize(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


async def _raise_for_status(response: httpx.Response, provider: str) -> None:
    if response.status_code != httpx.codes.OK:
        body = (await response.aread()).decode(errors="replace")[:200]
        raise ProviderError(f"{provider} request failed with {response.status_code}: {body}")


ReasoningEffort = Literal["none", "minimal", "low", "medium", "high"]


def reasoning_options(effort: ReasoningEffort) -> dict[str, Any]:
    if effort == "none":
        return {"enabled": False}
    return {"effort": effort, "exclude": True}


class OpenRouterChatModel:
    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        model: str,
        reasoning_effort: ReasoningEffort = "minimal",
    ) -> None:
        self._client = client
        self._reasoning = reasoning_options(reasoning_effort)
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._model = model

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[ChatEvent]:
        require_api_key(self._api_key)
        started = time.perf_counter()
        body = {
            "model": self._model,
            "messages": _serialize(messages),
            "stream": True,
            "reasoning": self._reasoning,
            "usage": {"include": True},
        }
        usage: dict[str, Any] = {}
        try:
            async with self._client.stream(
                "POST", self._url, headers=self._headers, json=body
            ) as response:
                await _raise_for_status(response, "OpenRouter")
                async for line in response.aiter_lines():
                    payload = self._parse_line(line)
                    if payload is None:
                        continue
                    for choice in payload.get("choices") or []:
                        text = (choice.get("delta") or {}).get("content")
                        if text:
                            yield TextDelta(text)
                    usage = payload.get("usage") or usage
        except httpx.HTTPError as error:
            raise ProviderError(f"OpenRouter stream failed: {error}") from error

        cost = usage.get("cost")
        yield UsageReport(
            Usage(
                provider="openrouter",
                model=self._model,
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                cost_usd=None if cost is None else Decimal(str(cost)),
                latency_ms=_elapsed_ms(started),
            )
        )

    @staticmethod
    def _parse_line(line: str) -> dict[str, Any] | None:
        if not line.startswith("data:"):
            return None
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            return None
        payload: dict[str, Any] = json.loads(data)
        if "error" in payload:
            raise ProviderError(f"OpenRouter stream error: {payload['error']}")
        return payload


class OllamaChatModel:
    def __init__(self, client: httpx.AsyncClient, base_url: str, model: str) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/api/chat"
        self._model = model

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[ChatEvent]:
        started = time.perf_counter()
        body = {
            "model": self._model,
            "messages": _serialize(messages),
            "stream": True,
            "think": False,
        }
        final: dict[str, Any] = {}
        try:
            async with self._client.stream("POST", self._url, json=body) as response:
                await _raise_for_status(response, "Ollama")
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    payload: dict[str, Any] = json.loads(line)
                    if "error" in payload:
                        raise ProviderError(f"Ollama stream error: {payload['error']}")
                    text = (payload.get("message") or {}).get("content")
                    if text:
                        yield TextDelta(text)
                    if payload.get("done"):
                        final = payload
        except httpx.HTTPError as error:
            raise ProviderError(f"Ollama stream failed: {error}") from error

        yield UsageReport(
            Usage(
                provider="ollama",
                model=self._model,
                input_tokens=int(final.get("prompt_eval_count", 0)),
                output_tokens=int(final.get("eval_count", 0)),
                cost_usd=Decimal(0),
                latency_ms=_elapsed_ms(started),
            )
        )

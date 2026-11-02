import time
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx

from app.llm.retry import RetryPolicy
from app.llm.types import ProviderError, Usage, require_api_key


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    usage: Usage


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> EmbeddingResult: ...


class OpenRouterEmbedder:
    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        batch_size: int,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._client = client
        self._retry = retry or RetryPolicy()
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        require_api_key(self._api_key)
        started = time.perf_counter()
        vectors: list[list[float]] = []
        input_tokens = 0
        cost = Decimal(0)
        cost_known = True

        for offset in range(0, len(texts), self._batch_size):
            payload = await self._request(list(texts[offset : offset + self._batch_size]))
            vectors.extend(self._vectors(payload))
            usage = payload.get("usage") or {}
            input_tokens += int(usage.get("prompt_tokens", 0))
            if usage.get("cost") is None:
                cost_known = False
            else:
                cost += Decimal(str(usage["cost"]))

        if len(vectors) != len(texts):
            raise ProviderError(f"Expected {len(texts)} embeddings, received {len(vectors)}")

        return EmbeddingResult(
            vectors=vectors,
            usage=Usage(
                provider="openrouter",
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=0,
                cost_usd=cost if cost_known else None,
                latency_ms=round((time.perf_counter() - started) * 1000),
            ),
        )

    async def _request(self, batch: list[str]) -> dict[str, Any]:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.post(
                    self._url, headers=self._headers, json={"model": self._model, "input": batch}
                )
            except httpx.TransportError as error:
                if not self._retry.should_retry(attempt):
                    raise ProviderError(f"Embedding request failed: {error}") from error
                await self._retry.wait(attempt)
                continue

            if response.status_code == httpx.codes.OK:
                payload: dict[str, Any] = response.json()
                return payload
            if not self._retry.should_retry(attempt, response.status_code):
                raise ProviderError(
                    f"Embedding request failed with {response.status_code}: {response.text[:200]}"
                )
            await self._retry.wait(attempt, response)

    def _vectors(self, payload: dict[str, Any]) -> list[list[float]]:
        items = sorted(payload.get("data") or [], key=lambda item: item["index"])
        vectors = [list(map(float, item["embedding"])) for item in items]
        for vector in vectors:
            if len(vector) != self._dimensions:
                raise ProviderError(
                    f"Expected {self._dimensions} dimensions, received {len(vector)}"
                )
        return vectors

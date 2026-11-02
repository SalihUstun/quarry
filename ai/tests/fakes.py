from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from decimal import Decimal
from uuid import UUID

from app.bootstrap import AppServices
from app.llm.embedder import EmbeddingResult
from app.llm.types import ProviderError, Usage
from app.services.ask import AskEvent

DIMENSIONS = 1024


def one_hot(position: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[position % DIMENSIONS] = 1.0
    return vector


def usage(model: str = "fake-model", input_tokens: int = 10, output_tokens: int = 0) -> Usage:
    return Usage(
        provider="fake",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=Decimal("0.00001"),
        latency_ms=5,
    )


class FakeEmbedder:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        self.calls.append(list(texts))
        if self.fail:
            raise ProviderError("Embedding provider unavailable")
        return EmbeddingResult(
            vectors=[one_hot(len(text)) for text in texts],
            usage=usage(model="fake-embedding", input_tokens=len(texts)),
        )


class FakeDatabase:
    def __init__(self, reachable: bool = True) -> None:
        self.reachable = reachable

    async def is_reachable(self) -> bool:
        return self.reachable


class FakeIngestor:
    def __init__(self) -> None:
        self.ingested: list[UUID] = []

    async def ingest(self, document_id: UUID) -> None:
        self.ingested.append(document_id)


class FakeAnswerer:
    def __init__(self, events: Sequence[AskEvent] = (), error: Exception | None = None) -> None:
        self.events = list(events)
        self.error = error
        self.calls: list[tuple[UUID, str, str]] = []

    async def answer(self, tenant_id: UUID, user_id: str, question: str) -> AsyncIterator[AskEvent]:
        self.calls.append((tenant_id, user_id, question))
        for event in self.events:
            yield event
        if self.error is not None:
            raise self.error


INTERNAL_TOKEN = "test-internal-token"


def services_factory(
    database: FakeDatabase | None = None,
    ingestor: FakeIngestor | None = None,
    answerer: FakeAnswerer | None = None,
) -> Callable[[], AbstractAsyncContextManager[AppServices]]:
    @asynccontextmanager
    async def factory() -> AsyncIterator[AppServices]:
        yield AppServices(
            database=database or FakeDatabase(),
            ingestion=ingestor or FakeIngestor(),
            ask=answerer or FakeAnswerer(),
            internal_token=INTERNAL_TOKEN,
        )

    return factory

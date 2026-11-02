from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.db.chunks import RetrievedChunk
from app.db.usage import Operation
from app.llm.chat import ChatModel
from app.llm.embedder import Embedder
from app.llm.types import TextDelta, Usage, UsageReport
from app.services.prompt import NO_ANSWER, build_messages, cited_source_numbers

SNIPPET_LENGTH = 280


class Retriever(Protocol):
    async def nearest(
        self, tenant_id: UUID, query_embedding: Sequence[float], limit: int
    ) -> list[RetrievedChunk]: ...


class UsageRecorder(Protocol):
    async def record(
        self, tenant_id: UUID, user_id: str, operation: Operation, usage: Usage
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class Source:
    number: int
    chunk_id: UUID
    document_id: UUID
    file_name: str
    page_number: int
    snippet: str


@dataclass(frozen=True, slots=True)
class SourcesFound:
    sources: list[Source]


@dataclass(frozen=True, slots=True)
class AnswerDelta:
    text: str


@dataclass(frozen=True, slots=True)
class AnswerCompleted:
    cited: list[int]


AskEvent = SourcesFound | AnswerDelta | AnswerCompleted


class AskService:
    def __init__(
        self,
        embedder: Embedder,
        retriever: Retriever,
        chat: ChatModel,
        usage: UsageRecorder,
        top_k: int,
    ) -> None:
        self._embedder = embedder
        self._retriever = retriever
        self._chat = chat
        self._usage = usage
        self._top_k = top_k

    async def answer(self, tenant_id: UUID, user_id: str, question: str) -> AsyncIterator[AskEvent]:
        embedding = await self._embedder.embed([question])
        await self._usage.record(tenant_id, user_id, "embedding", embedding.usage)

        chunks = await self._retriever.nearest(tenant_id, embedding.vectors[0], self._top_k)
        yield SourcesFound([_to_source(number, chunk) for number, chunk in enumerate(chunks, 1)])

        if not chunks:
            yield AnswerDelta(NO_ANSWER)
            yield AnswerCompleted(cited=[])
            return

        parts: list[str] = []
        async for event in self._chat.stream(build_messages(question, chunks)):
            if isinstance(event, TextDelta):
                parts.append(event.text)
                yield AnswerDelta(event.text)
            elif isinstance(event, UsageReport):
                await self._usage.record(tenant_id, user_id, "chat", event.usage)

        yield AnswerCompleted(cited=cited_source_numbers("".join(parts), len(chunks)))


def _to_source(number: int, chunk: RetrievedChunk) -> Source:
    snippet = chunk.content
    if len(snippet) > SNIPPET_LENGTH:
        snippet = snippet[:SNIPPET_LENGTH].rsplit(" ", 1)[0] + "…"
    return Source(
        number=number,
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        file_name=chunk.file_name,
        page_number=chunk.page_number,
        snippet=snippet,
    )

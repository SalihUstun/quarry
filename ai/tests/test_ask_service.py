from collections.abc import AsyncIterator, Sequence
from uuid import UUID, uuid4

import pytest

from app.db.chunks import RetrievedChunk
from app.db.usage import Operation
from app.llm.types import ChatEvent, ChatMessage, TextDelta, Usage, UsageReport
from app.services.ask import AnswerCompleted, AnswerDelta, AskEvent, AskService, SourcesFound
from app.services.prompt import NO_ANSWER
from tests.fakes import FakeEmbedder, usage

pytestmark = pytest.mark.anyio

TENANT_ID = uuid4()


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.calls: list[tuple[UUID, int]] = []

    async def nearest(
        self, tenant_id: UUID, query_embedding: Sequence[float], limit: int
    ) -> list[RetrievedChunk]:
        self.calls.append((tenant_id, limit))
        return self.chunks[:limit]


class FakeChat:
    def __init__(self, parts: list[str]) -> None:
        self.parts = parts
        self.messages: list[ChatMessage] = []

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[ChatEvent]:
        self.messages = list(messages)
        for part in self.parts:
            yield TextDelta(part)
        yield UsageReport(usage(model="fake-chat", input_tokens=100, output_tokens=20))


class RecordingUsage:
    def __init__(self) -> None:
        self.records: list[tuple[UUID, str, Operation, Usage]] = []

    async def record(
        self, tenant_id: UUID, user_id: str, operation: Operation, usage: Usage
    ) -> None:
        self.records.append((tenant_id, user_id, operation, usage))


def chunk(file_name: str, page: int, content: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        file_name=file_name,
        page_number=page,
        content=content,
        score=0.8,
    )


async def run(service: AskService, question: str = "Yıllık izin kaç gün?") -> list[AskEvent]:
    return [event async for event in service.answer(TENANT_ID, "ayse@ornek.com", question)]


async def test_answer_streams_sources_then_text_then_cited_numbers() -> None:
    chunks = [chunk("el-kitabi.pdf", 2, "Yılda 14 iş günü izin."), chunk("el-kitabi.pdf", 3, "x")]
    chat = FakeChat(["Yıllık izin 14 ", "iş günüdür [1]."])
    recorder = RecordingUsage()
    service = AskService(FakeEmbedder(), FakeRetriever(chunks), chat, recorder, top_k=5)

    events = await run(service)

    assert isinstance(events[0], SourcesFound)
    assert [(s.number, s.page_number) for s in events[0].sources] == [(1, 2), (2, 3)]
    assert [e.text for e in events if isinstance(e, AnswerDelta)] == [
        "Yıllık izin 14 ",
        "iş günüdür [1].",
    ]
    assert events[-1] == AnswerCompleted(cited=[1])
    assert [operation for _, _, operation, _ in recorder.records] == ["embedding", "chat"]
    assert "[1] (el-kitabi.pdf, sayfa 2)" in chat.messages[1].content


async def test_answer_without_matching_chunks_skips_llm() -> None:
    chat = FakeChat(["kullanılmamalı"])
    recorder = RecordingUsage()
    service = AskService(FakeEmbedder(), FakeRetriever([]), chat, recorder, top_k=5)

    events = await run(service)

    assert events == [SourcesFound([]), AnswerDelta(NO_ANSWER), AnswerCompleted(cited=[])]
    assert chat.messages == []
    assert [operation for _, _, operation, _ in recorder.records] == ["embedding"]


async def test_retrieval_is_scoped_to_tenant_and_top_k() -> None:
    retriever = FakeRetriever([chunk("a.pdf", 1, "metin")])
    service = AskService(FakeEmbedder(), retriever, FakeChat(["ok"]), RecordingUsage(), top_k=4)

    await run(service)

    assert retriever.calls == [(TENANT_ID, 4)]


async def test_long_chunks_are_trimmed_to_snippets() -> None:
    long_content = "kelime " * 200
    service = AskService(
        FakeEmbedder(),
        FakeRetriever([chunk("a.pdf", 1, long_content)]),
        FakeChat(["ok"]),
        RecordingUsage(),
        top_k=1,
    )

    events = await run(service)

    first = events[0]
    assert isinstance(first, SourcesFound)
    assert len(first.sources[0].snippet) <= 281
    assert first.sources[0].snippet.endswith("…")

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from app.services.ask import AskEvent


class DocumentIngestor(Protocol):
    async def ingest(self, document_id: UUID) -> None: ...


class QuestionAnswerer(Protocol):
    def answer(self, tenant_id: UUID, user_id: str, question: str) -> AsyncIterator[AskEvent]: ...

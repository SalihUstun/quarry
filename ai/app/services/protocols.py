from collections.abc import AsyncIterator, Sequence
from typing import Protocol
from uuid import UUID

from app.services.ask import AskEvent


class TextEmbedder(Protocol):
    async def embed(
        self, tenant_id: UUID, user_id: str, texts: Sequence[str]
    ) -> list[list[float]]: ...


class QuestionAnswerer(Protocol):
    def answer(self, tenant_id: UUID, user_id: str, question: str) -> AsyncIterator[AskEvent]: ...

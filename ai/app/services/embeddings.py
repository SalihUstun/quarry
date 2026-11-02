from collections.abc import Sequence
from uuid import UUID

from app.llm.embedder import Embedder
from app.services.ask import UsageRecorder


class EmbeddingService:
    def __init__(self, embedder: Embedder, usage: UsageRecorder) -> None:
        self._embedder = embedder
        self._usage = usage

    async def embed(self, tenant_id: UUID, user_id: str, texts: Sequence[str]) -> list[list[float]]:
        result = await self._embedder.embed(texts)
        await self._usage.record(tenant_id, user_id, "embedding", result.usage)
        return result.vectors

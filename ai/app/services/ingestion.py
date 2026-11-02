import asyncio
import logging
from pathlib import Path
from uuid import UUID

from app.db.documents import DocumentRecord, DocumentStore
from app.db.usage import UsageRepository
from app.ingestion.chunker import ChunkingConfig, chunk_pages
from app.ingestion.extract import ExtractionError, extract_pages
from app.llm.embedder import Embedder
from app.llm.types import ProviderError

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        documents: DocumentStore,
        embedder: Embedder,
        usage: UsageRepository,
        uploads_dir: Path,
        chunking: ChunkingConfig,
    ) -> None:
        self._documents = documents
        self._embedder = embedder
        self._usage = usage
        self._uploads_dir = uploads_dir.resolve()
        self._chunking = chunking

    async def ingest(self, document_id: UUID) -> None:
        document = await self._documents.claim_for_processing(document_id)
        if document is None:
            logger.info("Document not claimable", extra={"document_id": str(document_id)})
            return

        try:
            await self._process(document)
        except (ExtractionError, ProviderError) as error:
            await self._documents.mark_failed(document.id, str(error))
        except Exception:
            logger.exception("Ingestion failed", extra={"document_id": str(document.id)})
            await self._documents.mark_failed(document.id, "Unexpected processing error")

    async def _process(self, document: DocumentRecord) -> None:
        path = self._resolve_upload(document.storage_path)
        pages = await asyncio.to_thread(extract_pages, path, document.content_type)
        chunks = await asyncio.to_thread(chunk_pages, pages, self._chunking)
        if not chunks:
            raise ExtractionError("Document contains no extractable text")

        result = await self._embedder.embed([chunk.content for chunk in chunks])
        await self._usage.record(
            document.tenant_id, document.uploaded_by, "embedding", result.usage
        )
        await self._documents.complete(document, len(pages), chunks, result.vectors)

    def _resolve_upload(self, storage_path: str) -> Path:
        path = (self._uploads_dir / storage_path).resolve()
        if not path.is_relative_to(self._uploads_dir):
            raise ExtractionError("Storage path escapes the uploads directory")
        return path

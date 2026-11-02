from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.db.chunks import ChunkSearch
from app.db.database import Database, PostgresDatabase
from app.db.documents import DocumentStore
from app.db.usage import UsageRepository
from app.ingestion.chunker import ChunkingConfig
from app.llm.chat import ChatModel, OllamaChatModel, OpenRouterChatModel
from app.llm.embedder import OpenRouterEmbedder
from app.llm.retry import RetryPolicy
from app.services.ask import AskService
from app.services.ingestion import IngestionService
from app.services.protocols import DocumentIngestor, QuestionAnswerer


@dataclass(frozen=True, slots=True)
class AppServices:
    database: Database
    ingestion: DocumentIngestor
    ask: QuestionAnswerer
    internal_token: str


def build_chat_model(settings: Settings, client: httpx.AsyncClient) -> ChatModel:
    if settings.llm_provider == "ollama":
        return OllamaChatModel(client, settings.ollama_base_url, settings.llm_model)
    return OpenRouterChatModel(
        client,
        settings.openrouter_base_url,
        settings.openrouter_api_key.get_secret_value(),
        settings.llm_model,
        settings.llm_reasoning_effort,
        RetryPolicy(max_attempts=settings.llm_max_attempts),
    )


@asynccontextmanager
async def build_services(settings: Settings) -> AsyncIterator[AppServices]:
    database = PostgresDatabase(settings.database_url)
    await database.open()
    timeout = httpx.Timeout(settings.llm_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        embedder = OpenRouterEmbedder(
            client,
            settings.openrouter_base_url,
            settings.openrouter_api_key.get_secret_value(),
            settings.embedding_model,
            settings.embedding_dimensions,
            settings.embedding_batch_size,
            RetryPolicy(max_attempts=settings.llm_max_attempts),
        )
        usage = UsageRepository(database)
        try:
            yield AppServices(
                database=database,
                ingestion=IngestionService(
                    documents=DocumentStore(database),
                    embedder=embedder,
                    usage=usage,
                    uploads_dir=settings.uploads_dir,
                    chunking=ChunkingConfig(settings.chunk_max_chars, settings.chunk_overlap_chars),
                ),
                ask=AskService(
                    embedder=embedder,
                    retriever=ChunkSearch(database),
                    chat=build_chat_model(settings, client),
                    usage=usage,
                    top_k=settings.retrieval_top_k,
                ),
                internal_token=settings.internal_token.get_secret_value(),
            )
        finally:
            await database.close()

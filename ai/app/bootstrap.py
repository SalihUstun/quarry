from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.db.chunks import ChunkSearch
from app.db.database import Database, PostgresDatabase
from app.db.usage import UsageRepository
from app.llm.chat import ChatModel, OllamaChatModel, OpenRouterChatModel
from app.llm.embedder import OpenRouterEmbedder
from app.llm.retry import RetryPolicy
from app.services.ask import AskService
from app.services.embeddings import EmbeddingService
from app.services.protocols import QuestionAnswerer, TextEmbedder


@dataclass(frozen=True, slots=True)
class AppServices:
    database: Database
    embeddings: TextEmbedder
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
                embeddings=EmbeddingService(embedder, usage),
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

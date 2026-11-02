from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from psycopg.rows import class_row

from app.db.database import PostgresDatabase


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    file_name: str
    page_number: int
    content: str
    score: float


class ChunkSearch:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    async def nearest(
        self, tenant_id: UUID, query_embedding: Sequence[float], limit: int
    ) -> list[RetrievedChunk]:
        async with (
            self._database.connection() as connection,
            connection.cursor(row_factory=class_row(RetrievedChunk)) as cursor,
        ):
            await cursor.execute(
                """
                SELECT c.id AS chunk_id, c.document_id, d.file_name, c.page_number, c.content,
                       1 - (c.embedding <=> %(query)s) AS score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.tenant_id = %(tenant_id)s AND d.status = 'ready'
                ORDER BY c.embedding <=> %(query)s
                LIMIT %(limit)s
                """,
                {
                    "query": np.asarray(query_embedding, dtype=np.float32),
                    "tenant_id": tenant_id,
                    "limit": limit,
                },
            )
            return await cursor.fetchall()

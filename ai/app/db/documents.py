from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from psycopg.rows import class_row

from app.db.database import PostgresDatabase
from app.ingestion.chunker import Chunk


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    id: UUID
    tenant_id: UUID
    file_name: str
    content_type: str
    storage_path: str
    uploaded_by: str
    status: str


class DocumentStore:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    async def claim_for_processing(self, document_id: UUID) -> DocumentRecord | None:
        async with (
            self._database.connection() as connection,
            connection.cursor(row_factory=class_row(DocumentRecord)) as cursor,
        ):
            await cursor.execute(
                """
                UPDATE documents
                SET status = 'processing', error = NULL, updated_at = now()
                WHERE id = %s AND status IN ('pending', 'failed')
                RETURNING id, tenant_id, file_name, content_type, storage_path, uploaded_by, status
                """,
                (document_id,),
            )
            return await cursor.fetchone()

    async def complete(
        self,
        document: DocumentRecord,
        page_count: int,
        chunks: Sequence[Chunk],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk needs exactly one embedding")

        async with self._database.connection() as connection, connection.transaction():
            await connection.execute("DELETE FROM chunks WHERE document_id = %s", (document.id,))
            async with connection.cursor() as cursor:
                await cursor.executemany(
                    """
                    INSERT INTO chunks
                        (tenant_id, document_id, chunk_index, page_number, content, char_count,
                         embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            document.tenant_id,
                            document.id,
                            chunk.index,
                            chunk.page_number,
                            chunk.content,
                            chunk.char_count,
                            np.asarray(embedding, dtype=np.float32),
                        )
                        for chunk, embedding in zip(chunks, embeddings, strict=True)
                    ],
                )
            await connection.execute(
                """
                UPDATE documents
                SET status = 'ready', page_count = %s, error = NULL, updated_at = now()
                WHERE id = %s
                """,
                (page_count, document.id),
            )

    async def mark_failed(self, document_id: UUID, error: str) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                """
                UPDATE documents SET status = 'failed', error = %s, updated_at = now()
                WHERE id = %s
                """,
                (error[:1000], document_id),
            )

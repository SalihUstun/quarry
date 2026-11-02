from uuid import UUID

import pytest

from app.db.chunks import ChunkSearch
from app.db.database import PostgresDatabase
from app.db.documents import DocumentRecord, DocumentStore
from app.ingestion.chunker import Chunk
from tests.fakes import one_hot
from tests.integration.conftest import DEFAULT_TENANT_ID, create_document, create_tenant

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def store_chunks(
    database: PostgresDatabase,
    tenant_id: UUID,
    file_name: str,
    positions: list[int],
    status_after: str = "ready",
) -> UUID:
    document_id = await create_document(database, storage_path=file_name, tenant_id=tenant_id)
    record = DocumentRecord(
        id=document_id,
        tenant_id=tenant_id,
        file_name=file_name,
        content_type="application/pdf",
        storage_path=file_name,
        uploaded_by="tester@quarry.local",
        status="processing",
    )
    chunks = [
        Chunk(index=index, page_number=index + 1, content=f"{file_name} içerik {position}")
        for index, position in enumerate(positions)
    ]
    embeddings = [one_hot(position) for position in positions]
    await DocumentStore(database).complete(record, len(chunks), chunks, embeddings)
    if status_after != "ready":
        async with database.connection() as connection:
            await connection.execute(
                "UPDATE documents SET status = %s WHERE id = %s", (status_after, document_id)
            )
    return document_id


async def test_returns_most_similar_chunks_first_with_citation_fields(
    database: PostgresDatabase,
) -> None:
    await store_chunks(database, DEFAULT_TENANT_ID, "el-kitabi.pdf", [1, 2, 3])

    results = await ChunkSearch(database).nearest(DEFAULT_TENANT_ID, one_hot(2), limit=2)

    assert [result.content for result in results] == [
        "el-kitabi.pdf içerik 2",
        "el-kitabi.pdf içerik 1",
    ]
    assert results[0].file_name == "el-kitabi.pdf"
    assert results[0].page_number == 2
    assert results[0].score == pytest.approx(1.0)


async def test_never_returns_chunks_of_another_tenant(database: PostgresDatabase) -> None:
    other_tenant = await create_tenant(database, "Başka Şirket")
    await store_chunks(database, other_tenant, "gizli.pdf", [7])
    await store_chunks(database, DEFAULT_TENANT_ID, "acik.pdf", [100])

    results = await ChunkSearch(database).nearest(DEFAULT_TENANT_ID, one_hot(7), limit=10)

    assert {result.file_name for result in results} == {"acik.pdf"}


async def test_skips_documents_that_are_not_ready(database: PostgresDatabase) -> None:
    await store_chunks(database, DEFAULT_TENANT_ID, "isleniyor.pdf", [5], status_after="failed")

    results = await ChunkSearch(database).nearest(DEFAULT_TENANT_ID, one_hot(5), limit=10)

    assert results == []

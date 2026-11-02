import shutil
from pathlib import Path

import pytest

from app.db.database import PostgresDatabase
from app.db.documents import DocumentStore
from app.db.usage import UsageRepository
from app.ingestion.chunker import ChunkingConfig
from app.services.ingestion import IngestionService
from tests.fakes import FakeEmbedder
from tests.integration.conftest import create_document, fetch_one

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

SAMPLE_PDF = Path(__file__).resolve().parents[3] / "samples" / "calisan-el-kitabi.pdf"


def make_service(
    database: PostgresDatabase, uploads_dir: Path, embedder: FakeEmbedder
) -> IngestionService:
    return IngestionService(
        documents=DocumentStore(database),
        embedder=embedder,
        usage=UsageRepository(database),
        uploads_dir=uploads_dir,
        chunking=ChunkingConfig(),
    )


@pytest.fixture
def uploads_dir(tmp_path: Path) -> Path:
    shutil.copy(SAMPLE_PDF, tmp_path / "handbook.pdf")
    return tmp_path


async def test_pdf_is_chunked_embedded_and_marked_ready(
    database: PostgresDatabase, uploads_dir: Path
) -> None:
    document_id = await create_document(database, storage_path="handbook.pdf")
    embedder = FakeEmbedder()

    await make_service(database, uploads_dir, embedder).ingest(document_id)

    status, page_count, error = await fetch_one(
        database, "SELECT status, page_count, error FROM documents WHERE id = %s", document_id
    )
    assert (status, page_count, error) == ("ready", 3, None)
    (pages,) = await fetch_one(
        database,
        "SELECT array_agg(page_number ORDER BY chunk_index) FROM chunks WHERE document_id = %s",
        document_id,
    )
    assert pages == [1, 2, 3]
    operation, input_tokens = await fetch_one(
        database, "SELECT operation, input_tokens FROM llm_usage"
    )
    assert (operation, input_tokens) == ("embedding", 3)


async def test_already_processed_document_is_not_ingested_twice(
    database: PostgresDatabase, uploads_dir: Path
) -> None:
    document_id = await create_document(database, storage_path="handbook.pdf")
    embedder = FakeEmbedder()
    service = make_service(database, uploads_dir, embedder)

    await service.ingest(document_id)
    await service.ingest(document_id)

    assert len(embedder.calls) == 1
    (count,) = await fetch_one(
        database, "SELECT count(*) FROM chunks WHERE document_id = %s", document_id
    )
    assert count == 3


async def test_corrupt_file_marks_document_failed(
    database: PostgresDatabase, uploads_dir: Path
) -> None:
    (uploads_dir / "broken.pdf").write_bytes(b"%PDF-1.7 broken")
    document_id = await create_document(database, storage_path="broken.pdf")

    await make_service(database, uploads_dir, FakeEmbedder()).ingest(document_id)

    status, error = await fetch_one(
        database, "SELECT status, error FROM documents WHERE id = %s", document_id
    )
    assert status == "failed"
    assert "PDF could not be read" in str(error)


async def test_embedding_failure_marks_document_failed_without_chunks(
    database: PostgresDatabase, uploads_dir: Path
) -> None:
    document_id = await create_document(database, storage_path="handbook.pdf")

    await make_service(database, uploads_dir, FakeEmbedder(fail=True)).ingest(document_id)

    status, error = await fetch_one(
        database, "SELECT status, error FROM documents WHERE id = %s", document_id
    )
    assert (status, error) == ("failed", "Embedding provider unavailable")
    (count,) = await fetch_one(database, "SELECT count(*) FROM chunks")
    assert count == 0


async def test_storage_path_outside_uploads_dir_is_rejected(
    database: PostgresDatabase, uploads_dir: Path
) -> None:
    document_id = await create_document(database, storage_path="../../etc/passwd")

    await make_service(database, uploads_dir, FakeEmbedder()).ingest(document_id)

    status, error = await fetch_one(
        database, "SELECT status, error FROM documents WHERE id = %s", document_id
    )
    assert status == "failed"
    assert "escapes" in str(error)

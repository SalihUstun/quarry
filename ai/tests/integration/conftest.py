from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer

from app.db.database import PostgresDatabase

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "db" / "migrations"
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
MIGRATE_UP_MARKER = "-- migrate:up"
MIGRATE_DOWN_MARKER = "-- migrate:down"


def apply_migrations(url: str) -> None:
    with psycopg.connect(url, autocommit=True) as connection:
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            up_section = migration.read_text(encoding="utf-8").split(MIGRATE_DOWN_MARKER)[0]
            connection.execute(up_section.replace(MIGRATE_UP_MARKER, ""))


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:0.8.7-pg17", driver=None) as container:
        url = container.get_connection_url()
        apply_migrations(url)
        yield url


@pytest.fixture
async def database(postgres_url: str) -> AsyncIterator[PostgresDatabase]:
    database = PostgresDatabase(postgres_url)
    await database.open(wait=True)
    async with database.connection() as connection:
        await connection.execute("TRUNCATE llm_usage, chunks, documents")
        await connection.execute("DELETE FROM tenants WHERE id <> %s", (DEFAULT_TENANT_ID,))
    yield database
    await database.close()


async def create_tenant(database: PostgresDatabase, name: str) -> UUID:
    tenant_id = uuid4()
    async with database.connection() as connection:
        await connection.execute(
            "INSERT INTO tenants (id, name) VALUES (%s, %s)", (tenant_id, name)
        )
    return tenant_id


async def create_document(
    database: PostgresDatabase,
    storage_path: str = "doc.pdf",
    content_type: str = "application/pdf",
    tenant_id: UUID = DEFAULT_TENANT_ID,
    status: str = "pending",
) -> UUID:
    document_id = uuid4()
    async with database.connection() as connection:
        await connection.execute(
            """
            INSERT INTO documents
                (id, tenant_id, file_name, content_type, storage_path, size_bytes, status,
                 uploaded_by)
            VALUES (%s, %s, %s, %s, %s, 0, %s, 'tester@quarry.local')
            """,
            (document_id, tenant_id, Path(storage_path).name, content_type, storage_path, status),
        )
    return document_id


async def fetch_one(database: PostgresDatabase, query: str, *params: object) -> tuple[object, ...]:
    async with database.connection() as connection:
        cursor = await connection.execute(query, params)
        row = await cursor.fetchone()
    assert row is not None
    return tuple(row)

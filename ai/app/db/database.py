from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from psycopg import Error as PsycopgError
from psycopg_pool import AsyncConnectionPool


class Database(Protocol):
    async def is_reachable(self) -> bool: ...


class PostgresDatabase:
    def __init__(self, url: str, ping_timeout_seconds: float = 2.0) -> None:
        self._pool = AsyncConnectionPool(
            url, min_size=1, max_size=10, open=False, configure=register_vector_async
        )
        self._ping_timeout_seconds = ping_timeout_seconds

    async def open(self, wait: bool = False) -> None:
        await self._pool.open(wait=wait)

    async def close(self) -> None:
        await self._pool.close()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection]:
        async with self._pool.connection() as connection:
            yield connection

    async def is_reachable(self) -> bool:
        try:
            async with self._pool.connection(timeout=self._ping_timeout_seconds) as connection:
                await connection.execute("SELECT 1")
        except (PsycopgError, TimeoutError):
            return False
        return True

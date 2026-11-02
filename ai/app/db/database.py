from typing import Protocol

from psycopg import Error as PsycopgError
from psycopg_pool import AsyncConnectionPool


class Database(Protocol):
    async def open(self) -> None: ...

    async def close(self) -> None: ...

    async def is_reachable(self) -> bool: ...


class PostgresDatabase:
    def __init__(self, url: str, ping_timeout_seconds: float = 2.0) -> None:
        self._pool = AsyncConnectionPool(url, min_size=1, max_size=10, open=False)
        self._ping_timeout_seconds = ping_timeout_seconds

    async def open(self) -> None:
        await self._pool.open(wait=False)

    async def close(self) -> None:
        await self._pool.close()

    async def is_reachable(self) -> bool:
        try:
            async with self._pool.connection(timeout=self._ping_timeout_seconds) as connection:
                await connection.execute("SELECT 1")
        except (PsycopgError, TimeoutError):
            return False
        return True

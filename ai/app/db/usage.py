from typing import Literal
from uuid import UUID

from app.db.database import PostgresDatabase
from app.llm.types import Usage

Operation = Literal["chat", "embedding"]


class UsageRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    async def record(
        self, tenant_id: UUID, user_id: str, operation: Operation, usage: Usage
    ) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO llm_usage
                    (tenant_id, user_id, operation, provider, model, input_tokens, output_tokens,
                     cost_usd, latency_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    user_id,
                    operation,
                    usage.provider,
                    usage.model,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.cost_usd,
                    usage.latency_ms,
                ),
            )

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.core.config import Settings
from app.db.database import Database, PostgresDatabase


def create_app(database: Database | None = None) -> FastAPI:
    resolved_database = database or PostgresDatabase(Settings().database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await resolved_database.open()
        app.state.database = resolved_database
        yield
        await resolved_database.close()

    app = FastAPI(title="Quarry AI Service", lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()

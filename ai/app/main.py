from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from app.api import ask, health, internal
from app.bootstrap import AppServices, build_services
from app.core.config import Settings

ServicesFactory = Callable[[], AbstractAsyncContextManager[AppServices]]


def create_app(services_factory: ServicesFactory | None = None) -> FastAPI:
    factory = services_factory or (lambda: build_services(Settings()))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with factory() as services:
            app.state.services = services
            yield

    app = FastAPI(title="Quarry AI Service", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(internal.router)
    app.include_router(ask.router)
    return app


app = create_app()

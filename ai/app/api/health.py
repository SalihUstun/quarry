from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from app.db.database import Database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready")
async def readiness(
    response: Response,
    database: Annotated[Database, Depends(get_database)],
) -> HealthResponse:
    if await database.is_reachable():
        return HealthResponse(status="ok")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="database_unavailable")

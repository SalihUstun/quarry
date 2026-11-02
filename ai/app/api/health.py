from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.api.deps import ServicesDep

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready")
async def readiness(response: Response, services: ServicesDep) -> HealthResponse:
    if await services.database.is_reachable():
        return HealthResponse(status="ok")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="database_unavailable")

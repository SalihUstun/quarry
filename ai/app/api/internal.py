from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from pydantic import BaseModel

from app.api.deps import ServicesDep, require_internal_token

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_token)]
)


class IngestAccepted(BaseModel):
    document_id: UUID
    status: str = "accepted"


@router.post("/documents/{document_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    document_id: UUID, background_tasks: BackgroundTasks, services: ServicesDep
) -> IngestAccepted:
    background_tasks.add_task(services.ingestion.ingest, document_id)
    return IngestAccepted(document_id=document_id)

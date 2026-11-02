from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import IdentityDep, ServicesDep, require_internal_token
from app.llm.types import ProviderError

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_token)]
)


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=256)


class EmbeddingResponse(BaseModel):
    vectors: list[list[float]]


@router.post("/embeddings")
async def create_embeddings(
    request: EmbeddingRequest, identity: IdentityDep, services: ServicesDep
) -> EmbeddingResponse:
    try:
        vectors = await services.embeddings.embed(
            identity.tenant_id, identity.user_id, request.texts
        )
    except ProviderError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    return EmbeddingResponse(vectors=vectors)

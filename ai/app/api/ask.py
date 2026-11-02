import json
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import IdentityDep, ServicesDep, require_internal_token
from app.llm.types import ProviderError
from app.services.ask import AnswerCompleted, AnswerDelta, AskEvent, SourcesFound

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ask"], dependencies=[Depends(require_internal_token)])

STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def format_event(name: str, data: Any) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def to_sse(event: AskEvent) -> str:
    match event:
        case SourcesFound(sources):
            return format_event("sources", [asdict(source) for source in sources])
        case AnswerDelta(text):
            return format_event("token", {"text": text})
        case AnswerCompleted(cited):
            return format_event("done", {"cited": cited})


async def stream_answer(events: AsyncIterator[AskEvent]) -> AsyncIterator[str]:
    try:
        async for event in events:
            yield to_sse(event)
    except ProviderError:
        logger.exception("LLM provider failed while answering")
        yield format_event("error", {"message": "Yanıt üretilirken sağlayıcı hatası oluştu."})


@router.post("/ask")
async def ask(
    request: AskRequest, identity: IdentityDep, services: ServicesDep
) -> StreamingResponse:
    events = services.ask.answer(identity.tenant_id, identity.user_id, request.question.strip())
    return StreamingResponse(
        stream_answer(events), media_type="text/event-stream", headers=STREAM_HEADERS
    )

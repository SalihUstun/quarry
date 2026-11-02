import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.llm.types import ProviderError
from app.main import create_app
from app.services.ask import AnswerCompleted, AnswerDelta, Source, SourcesFound
from tests.fakes import INTERNAL_TOKEN, FakeAnswerer, FakeIngestor, services_factory

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
IDENTITY_HEADERS = {
    "X-Internal-Token": INTERNAL_TOKEN,
    "X-Tenant-Id": str(TENANT_ID),
    "X-User-Id": "ayse@ornek.com",
}


def parse_sse(body: str) -> list[tuple[str, object]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_ingest_endpoint_schedules_background_ingestion() -> None:
    ingestor = FakeIngestor()
    document_id = uuid4()

    with TestClient(create_app(services_factory(ingestor=ingestor))) as client:
        response = client.post(
            f"/internal/documents/{document_id}/ingest",
            headers={"X-Internal-Token": INTERNAL_TOKEN},
        )

    assert response.status_code == 202
    assert ingestor.ingested == [document_id]


@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_internal_endpoints_reject_missing_or_wrong_token(token: str | None) -> None:
    headers = {} if token is None else {"X-Internal-Token": token}

    with TestClient(create_app(services_factory())) as client:
        ingest = client.post(f"/internal/documents/{uuid4()}/ingest", headers=headers)
        ask = client.post("/ask", headers=headers, json={"question": "Soru?"})

    assert ingest.status_code == 401
    assert ask.status_code == 401


def test_ask_requires_identity_headers() -> None:
    with TestClient(create_app(services_factory())) as client:
        response = client.post(
            "/ask", headers={"X-Internal-Token": INTERNAL_TOKEN}, json={"question": "Soru?"}
        )

    assert response.status_code == 422


def test_ask_streams_sources_tokens_and_done_events() -> None:
    source = Source(
        number=1,
        chunk_id=uuid4(),
        document_id=uuid4(),
        file_name="el-kitabi.pdf",
        page_number=2,
        snippet="Yılda 14 iş günü izin verilir.",
    )
    answerer = FakeAnswerer(
        [
            SourcesFound([source]),
            AnswerDelta("Yıllık izin "),
            AnswerDelta("14 iş günüdür [1]."),
            AnswerCompleted(cited=[1]),
        ]
    )

    with TestClient(create_app(services_factory(answerer=answerer))) as client:
        response = client.post(
            "/ask", headers=IDENTITY_HEADERS, json={"question": "  İzin kaç gün?  "}
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["sources", "token", "token", "done"]
    sources = events[0][1]
    assert isinstance(sources, list)
    assert sources[0]["file_name"] == "el-kitabi.pdf"
    assert sources[0]["page_number"] == 2
    assert events[1][1] == {"text": "Yıllık izin "}
    assert events[3][1] == {"cited": [1]}
    assert answerer.calls == [(TENANT_ID, "ayse@ornek.com", "İzin kaç gün?")]


def test_ask_reports_provider_failure_as_error_event() -> None:
    answerer = FakeAnswerer([SourcesFound([])], error=ProviderError("boom"))

    with TestClient(create_app(services_factory(answerer=answerer))) as client:
        response = client.post("/ask", headers=IDENTITY_HEADERS, json={"question": "Soru?"})

    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["sources", "error"]


def test_ask_rejects_empty_question() -> None:
    with TestClient(create_app(services_factory())) as client:
        response = client.post("/ask", headers=IDENTITY_HEADERS, json={"question": ""})

    assert response.status_code == 422

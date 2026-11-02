import json
from decimal import Decimal

import httpx
import pytest

from app.llm.chat import (
    OllamaChatModel,
    OpenRouterChatModel,
    ReasoningEffort,
    reasoning_options,
)
from app.llm.types import ChatEvent, ChatMessage, ProviderError, TextDelta, UsageReport

pytestmark = pytest.mark.anyio

MESSAGES = [ChatMessage(role="user", content="Merhaba")]


async def collect(model: OpenRouterChatModel | OllamaChatModel) -> list[ChatEvent]:
    return [event async for event in model.stream(MESSAGES)]


def openrouter(handler: httpx.MockTransport) -> OpenRouterChatModel:
    return OpenRouterChatModel(
        client=httpx.AsyncClient(transport=handler),
        base_url="https://openrouter.test/api/v1",
        api_key="test-key",
        model="z-ai/glm-5.3-flash",
    )


def sse(*payloads: object) -> bytes:
    lines = [": OPENROUTER PROCESSING"]
    lines += [f"data: {json.dumps(payload)}" for payload in payloads]
    lines.append("data: [DONE]")
    return ("\n\n".join(lines) + "\n\n").encode()


async def test_openrouter_streams_text_and_reports_usage() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            content=sse(
                {"choices": [{"delta": {"content": "Yıllık "}}]},
                {"choices": [{"delta": {"content": "izin 14 gündür [1]."}}]},
                {
                    "choices": [],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 9, "cost": 0.000004},
                },
            ),
        )

    events = await collect(openrouter(httpx.MockTransport(handler)))

    assert [event.text for event in events if isinstance(event, TextDelta)] == [
        "Yıllık ",
        "izin 14 gündür [1].",
    ]
    report = events[-1]
    assert isinstance(report, UsageReport)
    assert (report.usage.input_tokens, report.usage.output_tokens) == (120, 9)
    assert report.usage.cost_usd == Decimal("0.000004")
    body = json.loads(requests[0].content)
    assert body["stream"] is True
    assert body["reasoning"] == {"effort": "minimal", "exclude": True}


async def test_openrouter_error_status_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"message": "Insufficient credits"}})

    with pytest.raises(ProviderError, match="402"):
        await collect(openrouter(httpx.MockTransport(handler)))


async def test_openrouter_error_inside_stream_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse({"error": {"message": "upstream timeout"}}))

    with pytest.raises(ProviderError, match="upstream timeout"):
        await collect(openrouter(httpx.MockTransport(handler)))


async def test_ollama_streams_ndjson_and_reports_token_counts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        lines = [
            {"message": {"content": "Merhaba"}, "done": False},
            {"message": {"content": "!"}, "done": False},
            {"message": {"content": ""}, "done": True, "prompt_eval_count": 12, "eval_count": 2},
        ]
        return httpx.Response(200, content="\n".join(json.dumps(line) for line in lines).encode())

    model = OllamaChatModel(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        base_url="http://ollama.test",
        model="qwen",
    )

    events = await collect(model)

    assert "".join(event.text for event in events if isinstance(event, TextDelta)) == "Merhaba!"
    report = events[-1]
    assert isinstance(report, UsageReport)
    assert (report.usage.input_tokens, report.usage.output_tokens) == (12, 2)
    assert report.usage.cost_usd == Decimal(0)


@pytest.mark.parametrize(
    ("effort", "expected"),
    [
        ("none", {"enabled": False}),
        ("minimal", {"effort": "minimal", "exclude": True}),
        ("high", {"effort": "high", "exclude": True}),
    ],
)
def test_reasoning_options(effort: ReasoningEffort, expected: dict[str, object]) -> None:
    assert reasoning_options(effort) == expected

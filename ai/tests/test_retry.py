import json

import httpx
import pytest

from app.llm.chat import OpenRouterChatModel
from app.llm.embedder import OpenRouterEmbedder
from app.llm.retry import RetryPolicy
from app.llm.types import ProviderError, TextDelta

pytestmark = pytest.mark.anyio


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def embedder(
    handler: httpx.MockTransport, sleep: RecordingSleep, attempts: int = 3
) -> OpenRouterEmbedder:
    return OpenRouterEmbedder(
        client=httpx.AsyncClient(transport=handler),
        base_url="https://openrouter.test/api/v1",
        api_key="test-key",
        model="baai/bge-m3",
        dimensions=2,
        batch_size=8,
        retry=RetryPolicy(max_attempts=attempts, sleep=sleep),
    )


def ok_embedding() -> httpx.Response:
    return httpx.Response(
        200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}], "usage": {"prompt_tokens": 1}}
    )


def responses(*items: httpx.Response | Exception) -> httpx.MockTransport:
    queue = list(items)

    def handler(request: httpx.Request) -> httpx.Response:
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.MockTransport(handler)


async def test_embedding_retries_rate_limit_then_succeeds() -> None:
    sleep = RecordingSleep()
    transport = responses(
        httpx.Response(429, json={"error": "Endpoint Busy"}),
        httpx.Response(503, text="unavailable"),
        ok_embedding(),
    )

    result = await embedder(transport, sleep).embed(["metin"])

    assert result.vectors == [[0.1, 0.2]]
    assert len(sleep.delays) == 2


async def test_embedding_honors_retry_after_header() -> None:
    sleep = RecordingSleep()
    transport = responses(httpx.Response(429, headers={"Retry-After": "3"}), ok_embedding())

    await embedder(transport, sleep).embed(["metin"])

    assert sleep.delays == [3.0]


async def test_embedding_retries_transport_errors() -> None:
    sleep = RecordingSleep()
    transport = responses(httpx.ConnectError("connection reset"), ok_embedding())

    result = await embedder(transport, sleep).embed(["metin"])

    assert result.vectors == [[0.1, 0.2]]
    assert len(sleep.delays) == 1


async def test_embedding_gives_up_after_max_attempts() -> None:
    sleep = RecordingSleep()
    transport = responses(*[httpx.Response(429, text="busy") for _ in range(3)])

    with pytest.raises(ProviderError, match="429"):
        await embedder(transport, sleep, attempts=3).embed(["metin"])

    assert len(sleep.delays) == 2


async def test_embedding_does_not_retry_client_errors() -> None:
    sleep = RecordingSleep()
    transport = responses(httpx.Response(401, text="invalid key"))

    with pytest.raises(ProviderError, match="401"):
        await embedder(transport, sleep).embed(["metin"])

    assert sleep.delays == []


async def test_chat_stream_retries_before_first_token() -> None:
    sleep = RecordingSleep()
    stream_body = "\n\n".join(
        [
            f"data: {json.dumps({'choices': [{'delta': {'content': 'Merhaba'}}]})}",
            "data: [DONE]",
        ]
    )
    model = OpenRouterChatModel(
        client=httpx.AsyncClient(
            transport=responses(
                httpx.Response(503, text="busy"), httpx.Response(200, text=stream_body)
            )
        ),
        base_url="https://openrouter.test/api/v1",
        api_key="test-key",
        model="z-ai/glm-5.3-flash",
        retry=RetryPolicy(max_attempts=3, sleep=sleep),
    )

    events = [event async for event in model.stream([])]

    assert [event.text for event in events if isinstance(event, TextDelta)] == ["Merhaba"]
    assert len(sleep.delays) == 1


@pytest.mark.parametrize(
    ("attempt", "low", "high"),
    [(1, 0.5, 1.0), (2, 1.0, 2.0), (3, 2.0, 4.0), (10, 7.5, 15.0)],
)
def test_backoff_grows_exponentially_with_jitter_and_cap(
    attempt: int, low: float, high: float
) -> None:
    policy = RetryPolicy(base_delay_seconds=1.0, max_delay_seconds=15.0)

    delays = [policy.delay_seconds(attempt) for _ in range(50)]

    assert all(low <= delay <= high for delay in delays)


def test_invalid_retry_after_falls_back_to_backoff() -> None:
    delay = RetryPolicy(base_delay_seconds=1.0).delay_seconds(1, "Wed, 21 Oct 2026 07:28:00 GMT")

    assert 0.5 <= delay <= 1.0

import json
from decimal import Decimal

import httpx
import pytest

from app.llm.embedder import OpenRouterEmbedder
from app.llm.types import ProviderError

pytestmark = pytest.mark.anyio


def make_embedder(handler: httpx.MockTransport, dimensions: int = 3) -> OpenRouterEmbedder:
    return OpenRouterEmbedder(
        client=httpx.AsyncClient(transport=handler),
        base_url="https://openrouter.test/api/v1",
        api_key="test-key",
        model="baai/bge-m3",
        dimensions=dimensions,
        batch_size=2,
    )


def embedding_response(request: httpx.Request) -> httpx.Response:
    texts = json.loads(request.content)["input"]
    data = [
        {"index": index, "embedding": [float(len(text)), 0.0, 1.0]}
        for index, text in reversed(list(enumerate(texts)))
    ]
    return httpx.Response(
        200, json={"data": data, "usage": {"prompt_tokens": len(texts) * 5, "cost": 0.0001}}
    )


async def test_embeds_in_batches_and_preserves_order() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return embedding_response(request)

    result = await make_embedder(httpx.MockTransport(handler)).embed(["a", "bb", "ccc"])

    assert [vector[0] for vector in result.vectors] == [1.0, 2.0, 3.0]
    assert len(requests) == 2
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert json.loads(requests[0].content)["model"] == "baai/bge-m3"
    assert result.usage.input_tokens == 15
    assert result.usage.cost_usd == Decimal("0.0002")


async def test_unknown_cost_is_reported_as_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}], "usage": {}}
        )

    result = await make_embedder(httpx.MockTransport(handler)).embed(["metin"])

    assert result.usage.cost_usd is None


async def test_http_error_status_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid key"})

    with pytest.raises(ProviderError, match="401"):
        await make_embedder(httpx.MockTransport(handler)).embed(["metin"])


async def test_wrong_dimension_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return embedding_response(request)

    with pytest.raises(ProviderError, match="dimensions"):
        await make_embedder(httpx.MockTransport(handler), dimensions=1024).embed(["metin"])

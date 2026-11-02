from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


class ProviderError(Exception):
    pass


MISSING_API_KEY_MESSAGE = "OPENROUTER_API_KEY is not configured"


def require_api_key(api_key: str) -> None:
    if not api_key:
        raise ProviderError(MISSING_API_KEY_MESSAGE)


@dataclass(frozen=True, slots=True)
class Usage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None
    latency_ms: int


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class UsageReport:
    usage: Usage


ChatEvent = TextDelta | UsageReport

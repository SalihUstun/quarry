import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

_jitter = random.SystemRandom()


def _default_sleep(seconds: float) -> Awaitable[None]:
    return asyncio.sleep(seconds)


def _parse_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 15.0
    sleep: Callable[[float], Awaitable[None]] = field(default=_default_sleep, compare=False)

    def should_retry(self, attempt: int, status_code: int | None = None) -> bool:
        if attempt >= self.max_attempts:
            return False
        return status_code is None or status_code in RETRYABLE_STATUS_CODES

    def delay_seconds(self, attempt: int, retry_after: str | None = None) -> float:
        requested = _parse_seconds(retry_after)
        if requested is not None:
            return min(requested, self.max_delay_seconds)
        exponential = min(math.ldexp(self.base_delay_seconds, attempt - 1), self.max_delay_seconds)
        return exponential * _jitter.uniform(0.5, 1.0)

    async def wait(self, attempt: int, response: httpx.Response | None = None) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        await self.sleep(self.delay_seconds(attempt, retry_after))

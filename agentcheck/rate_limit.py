"""Retry helpers for API rate limiting during parallel experiment runs."""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY_SECONDS = 2.0
DEFAULT_MAX_DELAY_SECONDS = 60.0


def default_rate_limit_retries() -> int:
    env = os.environ.get("AGENTCHECK_RATE_LIMIT_RETRIES")
    if env:
        return max(0, int(env))
    return DEFAULT_MAX_RETRIES


def is_rate_limit_error(exc: BaseException) -> bool:
    """Return True when an exception looks like an HTTP 429 / rate-limit response."""
    try:
        from openai import RateLimitError

        if isinstance(exc, RateLimitError):
            return True
    except ImportError:
        pass

    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(exc, "code", None)
    if status == 429:
        return True

    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None) == 429:
        return True

    message = str(exc).lower()
    return any(
        token in message
        for token in ("429", "rate limit", "rate_limit", "too many requests")
    )


def retry_on_rate_limit(
    fn: Callable[[], T],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn``, retrying with exponential backoff when rate-limited."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if not is_rate_limit_error(exc) or attempt >= max_retries:
                raise

            delay = min(max_delay_seconds, base_delay_seconds * (2**attempt))
            delay *= 0.5 + random.random()
            sleep(delay)
            attempt += 1

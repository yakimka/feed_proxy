from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import logging
import math
import os
import random
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

import httpx

from feed_proxy.deps import get_llm_cache_storage
from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler

if TYPE_CHECKING:
    from feed_proxy.entities import Post
    from feed_proxy.storage import LlmCacheStorage

logger = logging.getLogger(__name__)

_Number = TypeVar("_Number", int, float)

_DEFAULT_MAX_CONCURRENCY = 5

_DEFAULT_TEMPERATURE = 0.0

_DEFAULT_CACHE_TTL_DAYS = 7.0

_SECONDS_IN_DAY = 24 * 60 * 60

# How often expired cache entries are deleted while the process is running.
_CACHE_PURGE_INTERVAL_SECONDS = 60 * 60

_MIN_CACHE_TTL_DAYS = _CACHE_PURGE_INTERVAL_SECONDS / _SECONDS_IN_DAY

# Reasoning models can take well over 30 seconds for a long article.
_DEFAULT_TIMEOUT_SECONDS = 90.0

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

# Statuses meaning the provider as a whole is overloaded, not just this one request.
_BUSY_STATUSES = frozenset({429, 503})

_MAX_ATTEMPTS = 5

_BASE_RETRY_DELAY_SECONDS = 5.0

_MAX_RETRY_DELAY_SECONDS = 60.0

# The whole pipeline is sequential, so a stuck call must not hold it up for long.
_MAX_TOTAL_SECONDS = 180.0

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

_client: httpx.AsyncClient | None = None

_last_cache_purge = 0.0

_rng = random.SystemRandom()


@dataclasses.dataclass
class LlmPromptOptions(HandlerOptions):
    DESCRIPTIONS = {
        "source_field": ("Source field", "Post field or extras key to read text from"),
        "target_field": ("Target field", "Extras key to write the result to"),
        "prompt": (
            "Prompt",
            "Instruction for the model; must contain the {source} placeholder, "
            "which is replaced with the source text",
        ),
        "on_error_value": (
            "On error value",
            "Value written to target field on failure; defaults to the "
            "unprocessed source text",
        ),
    }

    source_field: str
    target_field: str
    prompt: str
    on_error_value: str | None = None


class _Retryable(Exception):
    def __init__(
        self,
        cause: Exception,
        *,
        retry_after: float | None = None,
        provider_busy: bool = False,
    ) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.retry_after = retry_after
        self.provider_busy = provider_busy


class _Cooldown:
    """Pause shared by all requests once the provider asked us to slow down."""

    def __init__(self) -> None:
        self._until = 0.0

    def block(self, seconds: float) -> None:
        self._until = max(self._until, _now() + seconds)

    async def wait(self) -> None:
        remaining = self._until - _now()
        if remaining > 0:
            await _sleep(remaining)


_cooldown = _Cooldown()


def _now() -> float:
    return time.monotonic()


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _jitter() -> float:
    return _rng.uniform(0.75, 1.25)


def _env_number(
    name: str,
    default: _Number,
    cast: Callable[[str], _Number],
    *,
    minimum: _Number,
) -> _Number:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = cast(raw)
    except ValueError:
        logger.warning("Invalid %s=%r, using default %s", name, raw, default)
        return default
    if not math.isfinite(value) or value < minimum:
        logger.warning("Invalid %s=%r, using default %s", name, raw, default)
        return default
    return value


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        timeout = _env_number(
            "LLM_TIMEOUT", _DEFAULT_TIMEOUT_SECONDS, float, minimum=1.0
        )
        _client = httpx.AsyncClient(
            base_url=os.environ["LLM_BASE_URL"].rstrip("/") + "/",
            headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
            timeout=timeout,
        )
    return _client


def _wall_time() -> float:
    return time.time()


def _make_cache_key(base_url: str, model: str, temperature: float, content: str) -> str:
    return hashlib.sha256(
        json.dumps([base_url, model, temperature, content]).encode()
    ).hexdigest()


async def _purge_expired_cache(cache: LlmCacheStorage, ttl_seconds: float) -> None:
    global _last_cache_purge
    now = _wall_time()
    if now - _last_cache_purge < _CACHE_PURGE_INTERVAL_SECONDS:
        return
    _last_cache_purge = now
    try:
        await cache.delete_older_than(now - ttl_seconds)
    except Exception:  # noqa: PIE786
        logger.exception("Failed to purge the LLM cache")


async def _read_cache(
    cache: LlmCacheStorage, key: str, ttl_seconds: float
) -> str | None:
    try:
        return await cache.get(key, newer_than=_wall_time() - ttl_seconds)
    except Exception:  # noqa: PIE786
        logger.exception("Failed to read from the LLM cache")
        return None


async def _write_cache(cache: LlmCacheStorage, key: str, value: str) -> None:
    try:
        await cache.set(key, value, created_at=_wall_time())
    except Exception:  # noqa: PIE786
        logger.exception("Failed to write to the LLM cache")


def _read_field(post: Post, name: str) -> str:
    extras = getattr(post, "extras", {})
    if name in extras:
        return extras[name]
    return getattr(post, name, "") or ""


def _status_error(response: httpx.Response) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(
        f"LLM responded with {response.status_code}: {response.text[:300]}",
        request=response.request,
        response=response,
    )


def _answer_text(content: Any) -> str:
    """Plain string, or a list of chunks as returned by reasoning models."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            chunk.get("text", "")
            for chunk in content
            if isinstance(chunk, dict) and chunk.get("type") == "text"
        )
    return ""


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return max(float(response.headers["Retry-After"]), 0.0)
    except (KeyError, ValueError):
        return None


def _retry_delay(exc: _Retryable, attempt: int) -> float:
    if exc.retry_after is not None:
        # never earlier than the provider asked, but spread the requests that
        # were waiting for the same moment
        delay = exc.retry_after * max(_jitter(), 1.0)
    else:
        delay = _BASE_RETRY_DELAY_SECONDS * 2 ** (attempt - 1) * _jitter()
    return min(delay, _MAX_RETRY_DELAY_SECONDS)


async def _attempt(client: httpx.AsyncClient, payload: dict[str, Any]) -> str:
    try:
        response = await client.post("chat/completions", json=payload)
    except httpx.RequestError as exc:  # timeouts, connection resets, bad encoding
        raise _Retryable(exc) from exc

    if response.status_code in _RETRY_STATUSES:
        raise _Retryable(
            _status_error(response),
            retry_after=_retry_after(response),
            provider_busy=response.status_code in _BUSY_STATUSES,
        )
    if response.is_error:
        raise _status_error(response)

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise _Retryable(
            ValueError(f"Unexpected response body: {response.text[:300]}")
        ) from exc
    answer = _answer_text(content)
    text = _THINK_BLOCK_RE.sub("", answer).strip()
    if not text:
        raise _Retryable(ValueError("Empty response from model"))
    return text


async def _request_answer(client: httpx.AsyncClient, payload: dict[str, Any]) -> str:
    started = _now()
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        await _cooldown.wait()
        try:
            return await _attempt(client, payload)
        except _Retryable as exc:
            delay = _retry_delay(exc, attempt)
            out_of_time = _now() - started + delay > _MAX_TOTAL_SECONDS
            if attempt == _MAX_ATTEMPTS or out_of_time:
                raise exc.cause from None
            if exc.provider_busy:
                _cooldown.block(delay)
            logger.warning(
                "LLM call failed (%s: %s), retrying in %.1fs (attempt %s/%s)",
                type(exc.cause).__name__,
                exc,
                delay,
                attempt,
                _MAX_ATTEMPTS,
            )
            await _sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


async def _run_prompt(prompt: str, source: str) -> str:
    client = _get_client()
    model = os.environ["LLM_MODEL"]
    temperature = _env_number(
        "LLM_TEMPERATURE", _DEFAULT_TEMPERATURE, float, minimum=0.0
    )
    content = prompt.replace("{source}", source)
    cache = get_llm_cache_storage()
    key = _make_cache_key(str(client.base_url), model, temperature, content)
    ttl_seconds = _SECONDS_IN_DAY * _env_number(
        "LLM_CACHE_TTL_DAYS",
        _DEFAULT_CACHE_TTL_DAYS,
        float,
        minimum=_MIN_CACHE_TTL_DAYS,
    )
    await _purge_expired_cache(cache, ttl_seconds)
    cached = await _read_cache(cache, key, ttl_seconds)
    if cached is not None:
        logger.info("Using the cached LLM answer")
        return cached
    text = await _request_answer(
        client,
        {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
        },
    )
    await _write_cache(cache, key, text)
    return text


async def _process_post(
    post: Post, options: LlmPromptOptions, semaphore: asyncio.Semaphore
) -> None:
    source = _read_field(post, options.source_field)
    extras: dict[str, str] = getattr(post, "extras", {})
    if not source:
        extras[options.target_field] = source
        return
    async with semaphore:
        try:
            result = await _run_prompt(options.prompt, source)
        except Exception:  # noqa: PIE786
            logger.exception(
                "Failed to run llm_prompt for field %s of post %s",
                options.source_field,
                post,
            )
            result = (
                options.on_error_value if options.on_error_value is not None else source
            )
        else:
            logger.info(
                "Successfully ran llm_prompt for field %s",
                options.source_field,
            )
    extras[options.target_field] = result


@register_handler(
    type=HandlerType.pre_send_processors,
    options=LlmPromptOptions,
)
async def llm_prompt(posts: list[Post], *, options: LlmPromptOptions) -> list[Post]:
    semaphore = asyncio.Semaphore(
        _env_number("LLM_MAX_CONCURRENCY", _DEFAULT_MAX_CONCURRENCY, int, minimum=1)
    )
    await asyncio.gather(*(_process_post(post, options, semaphore) for post in posts))
    return posts

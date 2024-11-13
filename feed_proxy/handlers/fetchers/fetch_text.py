import asyncio
import dataclasses
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler
from feed_proxy.logic import fetch_text_from_url
from feed_proxy.utils.http import domain_from_url

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class FetchTextOptions(HandlerOptions):
    DESCRIPTIONS = {
        "url": ("URL", ""),
        "encoding": ("Page encoding", ""),
    }

    url: str
    encoding: str = ""


@register_handler(
    type=HandlerType.fetchers,
    name="fetch_text",
    options=FetchTextOptions,
)
class TextFetcher:
    def __init__(self, pause_between_domain_calls_sec: float = 1.0):
        self._requests_limiter = _RequestsLimiter()
        self._pause_between_domain_calls_sec = pause_between_domain_calls_sec

    async def __call__(self, *, options: FetchTextOptions) -> str | None:
        async with self._requests_limiter(
            options.url, self._pause_between_domain_calls_sec
        ):
            return await fetch_text_from_url(
                options.url, encoding=options.encoding, retry=2
            )


class _RequestsLimiter:
    def __init__(self) -> None:
        self.domains: dict[str, float] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def __call__(
        self, url: str, pause_between_domain_calls_sec: float
    ) -> AsyncIterator[None]:
        domain = domain_from_url(url)
        lock = self.locks.setdefault(domain, asyncio.Lock())
        async with lock:
            if time_to_wait := self._get_left_to_wait(
                domain, pause_between_domain_calls_sec
            ):
                logger.info("Waiting %s sec before fetching %s", time_to_wait, url)
                await asyncio.sleep(time_to_wait)
            yield
            self.domains[domain] = time.time()

    def _get_left_to_wait(self, key: str, pause_sec: float) -> float | None:
        last_call_time_delta = self._get_last_call_time_delta(key)
        if last_call_time_delta < pause_sec:
            return pause_sec - last_call_time_delta
        return None

    def _get_last_call_time_delta(self, key: str) -> float:
        return time.time() - self.domains.get(key, 0)

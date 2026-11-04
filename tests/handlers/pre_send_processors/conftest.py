import asyncio
import json
from typing import Any

import httpx
import pytest

from feed_proxy.handlers.parsers.rss import FeedPost
from feed_proxy.handlers.pre_send_processors.llm_prompt import LlmPromptOptions


@pytest.fixture()
def make_feed_post():
    def _make_feed_post(**kwargs: Any) -> FeedPost:
        defaults = {
            "post_id": "post_id",
            "title": "Post title",
            "url": "https://post.url",
            "comments_url": "https://post.url/comments",
            "post_tags": ["tag1", "tag2"],
            "source_tags": ["source1"],
        }
        return FeedPost(**{**defaults, **kwargs})

    return _make_feed_post


@pytest.fixture()
def make_llm_prompt_options():
    def _make_llm_prompt_options(**kwargs: Any) -> LlmPromptOptions:
        defaults = {
            "source_field": "title",
            "target_field": "title_ua",
            "prompt": "Translate the following text to Ukrainian. "
            "Output only the translation, no explanations.\n\nText:\n{source}",
        }
        return LlmPromptOptions(**{**defaults, **kwargs})

    return _make_llm_prompt_options


class StubLlm:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []
        self.clock = 0.0
        self.max_in_flight = 0
        self._in_flight = 0
        self._status_code = 200
        self._headers: dict[str, str] = {}
        self._body: Any = None
        self._queue: list[httpx.Response | BaseException] = []
        self._exception: BaseException | None = None

    def set_response(self, text: str | list[Any] | None) -> None:
        """Answer every request with this text, once the queue is empty."""
        self._status_code = 200
        self._headers = {}
        self._body = {"choices": [{"message": {"content": text}}]}

    def set_status(
        self,
        status_code: int,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Answer every request with this status, once the queue is empty."""
        self._status_code = status_code
        self._body = body or {"error": {"message": "failure"}}
        self._headers = headers or {}

    def set_exception(self, exc: BaseException) -> None:
        """Fail every request with this exception, once the queue is empty."""
        self._exception = exc

    def queue_status(
        self, status_code: int, headers: dict[str, str] | None = None
    ) -> None:
        """Answer the next request with this status, before the default response."""
        self._queue.append(
            httpx.Response(status_code, json={"error": {}}, headers=headers)
        )

    def queue_answer(self, text: str | None) -> None:
        """Answer the next request with this text, before the default response."""
        self._queue.append(
            httpx.Response(200, json={"choices": [{"message": {"content": text}}]})
        )

    def queue_raw(self, text: str) -> None:
        """Answer the next request with a 200 and this raw body."""
        self._queue.append(httpx.Response(200, text=text))

    def queue_exception(self, exc: BaseException) -> None:
        """Fail the next request with this exception."""
        self._queue.append(exc)

    @property
    def prompts(self) -> list[str]:
        return [
            json.loads(request.content)["messages"][0]["content"]
            for request in self.requests
        ]

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self._in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self._in_flight)
        try:
            await asyncio.sleep(0)
            if self._queue:
                item = self._queue.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item
            if self._exception is not None:
                raise self._exception
            return httpx.Response(
                self._status_code, json=self._body, headers=self._headers
            )
        finally:
            self._in_flight -= 1

    def now(self) -> float:
        return self.clock

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        # let the other requests run while this one "sleeps"
        for _ in range(10):
            await asyncio.sleep(0)
        self.clock += seconds


@pytest.fixture()
def make_stub_llm(monkeypatch):
    def _make_stub_llm(base_url: str = "https://llm.test/v1/") -> StubLlm:
        llm = StubLlm()
        client = httpx.AsyncClient(
            base_url=base_url,
            transport=httpx.MockTransport(llm.handle),
        )
        module = "feed_proxy.handlers.pre_send_processors.llm_prompt"
        monkeypatch.setattr(f"{module}._get_client", lambda: client)
        monkeypatch.setattr(f"{module}._sleep", llm.sleep)
        monkeypatch.setattr(f"{module}._now", llm.now)
        monkeypatch.setattr(f"{module}._jitter", lambda: 1.0)
        monkeypatch.setattr(f"{module}._cooldown._until", 0.0)
        monkeypatch.setenv("LLM_MODEL", "test-model")
        return llm

    return _make_stub_llm


@pytest.fixture()
def stub_llm(make_stub_llm):
    return make_stub_llm()

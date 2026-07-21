from typing import Any
from unittest.mock import AsyncMock

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


@pytest.fixture()
def stub_gemini(monkeypatch):
    client = AsyncMock()

    def _set_response(text: str) -> None:
        client.aio.models.generate_content.return_value.text = text

    def _set_exception(exc: BaseException) -> None:
        client.aio.models.generate_content.side_effect = exc

    monkeypatch.setattr(
        "feed_proxy.handlers.pre_send_processors.llm_prompt._get_client",
        lambda: client,
    )

    client.set_response = _set_response
    client.set_exception = _set_exception
    return client

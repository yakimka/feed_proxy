from typing import Any
from unittest.mock import AsyncMock

import pytest

from feed_proxy.handlers.parsers.rss import FeedPost
from feed_proxy.handlers.pre_send_processors.translator import TranslatorOptions


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
def make_translator_options():
    def _make_translator_options(**kwargs: Any) -> TranslatorOptions:
        defaults = {
            "source_field": "title",
            "target_field": "title_ua",
            "target_language": "uk",
        }
        return TranslatorOptions(**{**defaults, **kwargs})

    return _make_translator_options


@pytest.fixture()
def stub_gemini(monkeypatch):
    client = AsyncMock()

    def _set_response(text: str) -> None:
        client.aio.models.generate_content.return_value.text = text

    def _set_exception(exc: BaseException) -> None:
        client.aio.models.generate_content.side_effect = exc

    monkeypatch.setattr(
        "feed_proxy.handlers.pre_send_processors.translator._get_client",
        lambda: client,
    )

    client.set_response = _set_response
    client.set_exception = _set_exception
    return client

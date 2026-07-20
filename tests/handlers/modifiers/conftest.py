from typing import Any

import pytest

from feed_proxy.handlers.modifiers.regex_replace import RegexReplaceOptions
from feed_proxy.handlers.modifiers.strip_html import StripHtmlOptions
from feed_proxy.handlers.parsers.rss import FeedPost


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
def make_regex_replace_options():
    def _make_regex_replace_options(**kwargs: Any) -> RegexReplaceOptions:
        defaults = {
            "field": "description",
            "pattern": "",
        }
        return RegexReplaceOptions(**{**defaults, **kwargs})

    return _make_regex_replace_options


@pytest.fixture()
def make_strip_html_options():
    def _make_strip_html_options(**kwargs: Any) -> StripHtmlOptions:
        defaults = {
            "field": "description",
        }
        return StripHtmlOptions(**{**defaults, **kwargs})

    return _make_strip_html_options

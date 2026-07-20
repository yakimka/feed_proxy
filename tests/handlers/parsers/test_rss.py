from typing import Any

import pytest

from feed_proxy.handlers.parsers.rss import FeedPost, _handler


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


def test_template_kwargs_without_extras(make_feed_post):
    post = make_feed_post(description="Some description")

    result = post.template_kwargs()

    assert result == {
        "post_id": "post_id",
        "title": "Post title",
        "url": "https://post.url",
        "comments_url": "https://post.url/comments",
        "post_tags": "tag1; tag2",
        "source_tags": "source1",
        "post_hash_tags": "#tag1 #tag2",
        "source_hash_tags": "#source1",
        "description": "Some description",
    }


def test_template_kwargs_with_extras_adding_new_key(make_feed_post):
    post = make_feed_post(extras={"title_ua": "Заголовок"})

    result = post.template_kwargs()

    assert result["title_ua"] == "Заголовок"
    assert result["title"] == "Post title"


def test_template_kwargs_with_extras_overriding_base_field(make_feed_post):
    post = make_feed_post(extras={"title": "Overridden title"})

    result = post.template_kwargs()

    assert result["title"] == "Overridden title"


def _make_rss_text(description_tag: str = "description") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test feed</title>
    <item>
      <guid>https://post.url/1</guid>
      <title>Post title</title>
      <link>https://post.url/1</link>
      <{description_tag}>Post summary text</{description_tag}>
    </item>
  </channel>
</rss>
"""


def test_description_populated_from_summary():
    posts = _handler(_make_rss_text("description"))

    assert posts[0].description == "Post summary text"


def test_description_defaults_to_empty_string():
    text = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test feed</title>
    <item>
      <guid>https://post.url/1</guid>
      <title>Post title</title>
      <link>https://post.url/1</link>
    </item>
  </channel>
</rss>
"""

    posts = _handler(text)

    assert posts[0].description == ""

import json
from typing import Any

import pytest

from feed_proxy.handlers.parsers.wordpress import WordpressPost, wordpress


@pytest.fixture()
def make_wordpress_post():
    def _make_wordpress_post(**kwargs: Any) -> WordpressPost:
        defaults = {
            "post_id": "post_id",
            "title": "Post title",
            "url": "https://post.url",
            "source_tags": ["source1"],
        }
        return WordpressPost(**{**defaults, **kwargs})

    return _make_wordpress_post


def _make_wp_posts_json() -> str:
    return json.dumps(
        [
            {
                "id": 1,
                "title": {"rendered": "First post &#8217;s title"},
                "link": "https://blog.example/first-post",
                "excerpt": {"rendered": "<p>First excerpt&#8230;</p>"},
                "content": {"rendered": "<p>First content</p>"},
            },
            {
                "id": 2,
                "title": {"rendered": "Second &amp; post"},
                "link": "https://blog.example/second-post",
                "excerpt": {"rendered": "<p>Second excerpt&#8230;</p>"},
                "content": {"rendered": "<p>Second content</p>"},
            },
        ]
    )


async def test_full_field_mapping():
    posts = await wordpress(_make_wp_posts_json())

    assert posts[0].post_id == "1"
    assert posts[0].title == "First post ’s title"
    assert posts[0].url == "https://blog.example/first-post"
    assert posts[0].description == "<p>First excerpt&#8230;</p>"
    assert posts[0].content == "<p>First content</p>"
    assert posts[0].source_tags == []
    assert posts[1].post_id == "2"


async def test_title_is_html_unescaped():
    posts = await wordpress(_make_wp_posts_json())

    assert posts[0].title == "First post ’s title"
    assert posts[1].title == "Second & post"


async def test_empty_array_returns_empty_list():
    posts = await wordpress("[]")

    assert posts == []


async def test_non_list_error_payload_returns_empty_list():
    error_payload = json.dumps({"code": "rest_invalid_param", "message": "Invalid"})

    posts = await wordpress(error_payload)

    assert posts == []


def test_template_kwargs_without_extras(make_wordpress_post):
    post = make_wordpress_post(description="Some description", content="Some content")

    result = post.template_kwargs()

    assert result == {
        "post_id": "post_id",
        "title": "Post title",
        "url": "https://post.url",
        "source_tags": "source1",
        "source_hash_tags": "#source1",
        "description": "Some description",
        "content": "Some content",
    }


def test_template_kwargs_with_extras_adding_new_key(make_wordpress_post):
    post = make_wordpress_post(extras={"title_ua": "Заголовок"})

    result = post.template_kwargs()

    assert result["title_ua"] == "Заголовок"
    assert result["title"] == "Post title"


def test_template_kwargs_with_extras_overriding_base_field(make_wordpress_post):
    post = make_wordpress_post(extras={"title": "Overridden title"})

    result = post.template_kwargs()

    assert result["title"] == "Overridden title"

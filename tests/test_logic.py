from __future__ import annotations

from collections import defaultdict
from functools import partial
from typing import Any

import pytest

from feed_proxy import logic
from feed_proxy.entities import Post, PreSendProcessor
from feed_proxy.handlers import HandlerType
from feed_proxy.handlers.parsers.rss import FeedPost
from feed_proxy.storage import MemoryPostStorage
from feed_proxy.test import ObjectMother


@pytest.fixture()
def mother() -> ObjectMother:
    return ObjectMother()


@pytest.fixture()
def make_post():
    def _make_post(post_id: str = "post_id", **kwargs: Any) -> Post:
        defaults: dict[str, Any] = {
            "post_id": post_id,
            "title": "Post title",
            "url": "https://post.url",
            "comments_url": "",
            "post_tags": [],
            "source_tags": [],
        }
        return FeedPost(**{**defaults, **kwargs})

    return _make_post


@pytest.fixture()
def handler_registry(monkeypatch):
    registry: dict[HandlerType, dict[str, Any]] = defaultdict(dict)

    def fake_get_handler_by_name(
        *, type: HandlerType, name: str, options: dict | None = None
    ) -> Any:
        return partial(registry[type][name], options=options)

    monkeypatch.setattr(logic, "get_handler_by_name", fake_get_handler_by_name)
    return registry


async def test_processors_see_only_unprocessed_posts(
    mother, make_post, handler_registry
):
    seen: list[Post] = []

    async def recorder(posts: list[Post], *, options=None) -> list[Post]:  # noqa: U100
        seen.extend(posts)
        return posts

    handler_registry[HandlerType.pre_send_processors]["recorder"] = recorder
    source = mother.source()
    stream = mother.stream(
        pre_send_processors=[mother.pre_send_processor("recorder", {})]
    )
    storage = MemoryPostStorage()
    key = (source.id, stream.receiver_type)
    processed_post = make_post(post_id="processed")
    new_post = make_post(post_id="new")
    await storage.mark_posts_as_processed(key, [processed_post.post_id])

    await logic.parse_message_batches_from_posts(
        [processed_post, new_post], source, stream, storage
    )

    assert seen == [new_post]


async def test_no_processors_behavior_is_unchanged(mother, make_post):
    source = mother.source()
    stream = mother.stream()
    storage = MemoryPostStorage()
    key = (source.id, stream.receiver_type)
    await storage.mark_posts_as_processed(key, ["seed"])
    post = make_post(post_id="new", title="Hello")

    batches = await logic.parse_message_batches_from_posts(
        [post], source, stream, storage
    )

    assert len(batches) == 1
    assert len(batches[0]) == 1
    message = batches[0][0]
    assert message.post_id == "new"
    assert message.template_kwargs["title"] == "Hello"
    assert await storage.is_post_processed(key, "new")


async def test_processor_writes_extras_visible_in_message(
    mother, make_post, handler_registry
):
    async def add_extra(posts: list[Post], *, options=None) -> list[Post]:  # noqa: U100
        for post in posts:
            post.extras["x"] = "v"
        return posts

    handler_registry[HandlerType.pre_send_processors]["add_extra"] = add_extra
    source = mother.source()
    stream = mother.stream(
        pre_send_processors=[mother.pre_send_processor("add_extra", {})]
    )
    storage = MemoryPostStorage()
    key = (source.id, stream.receiver_type)
    await storage.mark_posts_as_processed(key, ["seed"])
    post = make_post(post_id="new")

    batches = await logic.parse_message_batches_from_posts(
        [post], source, stream, storage
    )

    assert batches[0][0].template_kwargs["x"] == "v"


async def test_apply_pre_send_processors_runs_in_declared_order(
    make_post, handler_registry
):
    async def append_a(posts: list[Post], *, options=None) -> list[Post]:  # noqa: U100
        for post in posts:
            post.extras["log"] = post.extras.get("log", "") + "a"
        return posts

    async def append_b(posts: list[Post], *, options=None) -> list[Post]:  # noqa: U100
        for post in posts:
            post.extras["log"] = post.extras.get("log", "") + "b"
        return posts

    handler_registry[HandlerType.pre_send_processors]["append_a"] = append_a
    handler_registry[HandlerType.pre_send_processors]["append_b"] = append_b
    processors = [
        PreSendProcessor(type="append_a", options={}),
        PreSendProcessor(type="append_b", options={}),
    ]
    post = make_post()

    result = await logic.apply_pre_send_processors(processors, [post])

    assert result[0].extras["log"] == "ab"


async def test_unhandled_processor_exception_aborts_before_marking(
    mother, make_post, handler_registry
):
    class StubStorage:
        def __init__(self) -> None:
            self._processed: set[str] = {"seed"}
            self.mark_calls: list[list[str]] = []

        async def has_posts(self, key) -> bool:  # noqa: U100
            return True

        async def is_post_processed(self, key, post_id) -> bool:  # noqa: U100
            return post_id in self._processed

        async def mark_posts_as_processed(self, key, post_ids) -> None:  # noqa: U100
            self.mark_calls.append(post_ids)
            self._processed.update(post_ids)

    async def boom(posts: list[Post], *, options=None) -> list[Post]:  # noqa: U100
        raise RuntimeError("boom")

    handler_registry[HandlerType.pre_send_processors]["boom"] = boom
    source = mother.source()
    stream = mother.stream(pre_send_processors=[mother.pre_send_processor("boom", {})])
    storage = StubStorage()
    post = make_post(post_id="new")

    with pytest.raises(RuntimeError):
        await logic.parse_message_batches_from_posts([post], source, stream, storage)

    assert storage.mark_calls == []


def test_post_identities_default_dedup_key_is_post_id_only(make_post):
    post = make_post(post_id="post-1", title="Some title")

    assert logic.post_identities(post, "post_id") == ["post-1"]


def test_post_identities_title_dedup_key_adds_normalized_title(make_post):
    post = make_post(post_id="post-1", title="  Some   Title  ")

    identities = logic.post_identities(post, "title")

    assert identities == ["post-1", "title:some title"]


def test_post_identities_title_dedup_key_empty_title(make_post):
    post = make_post(post_id="post-1", title="")

    assert logic.post_identities(post, "title") == ["post-1"]


def test_post_identities_title_dedup_key_whitespace_only_title(make_post):
    post = make_post(post_id="post-1", title="   ")

    assert logic.post_identities(post, "title") == ["post-1"]


async def test_cross_stream_isolation(mother, make_post, handler_registry):
    async def add_marker(posts: list[Post], *, options=None) -> list[Post]:
        for post in posts:
            post.extras["marker"] = (options or {}).get("marker", "")
        return posts

    async def stub_parser(text, *, options=None) -> list[Post]:  # noqa: U100
        return [make_post(post_id="shared")]

    handler_registry[HandlerType.pre_send_processors]["add_marker"] = add_marker
    handler_registry[HandlerType.parsers]["stub_parser"] = stub_parser

    stream_a = mother.stream(
        receiver_type="stream_a",
        pre_send_processors=[mother.pre_send_processor("add_marker", {"marker": "a"})],
    )
    stream_b = mother.stream(receiver_type="stream_b")
    source = mother.source(parser_type="stub_parser", streams=[stream_a, stream_b])
    storage = MemoryPostStorage()
    await storage.mark_posts_as_processed((source.id, "stream_a"), ["seed"])
    await storage.mark_posts_as_processed((source.id, "stream_b"), ["seed"])

    parsed = await logic.parse_posts(source, "irrelevant")

    batches_by_stream = {}
    for stream, posts in parsed:
        batches_by_stream[stream.receiver_type] = (
            await logic.parse_message_batches_from_posts(posts, source, stream, storage)
        )

    assert batches_by_stream["stream_a"][0][0].template_kwargs["marker"] == "a"
    assert "marker" not in batches_by_stream["stream_b"][0][0].template_kwargs

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from feed_proxy.configuration import load_configuration
from feed_proxy.logic import (
    fetch_text,
    parse_messages_from_posts,
    parse_posts,
    send_messages,
)

if TYPE_CHECKING:
    from feed_proxy.entities import Message, Post, Source, Stream  # noqa: TC004


class TextUnit(NamedTuple):
    text: str
    source: Source


class PostsUnit(NamedTuple):
    posts: list[Post]
    stream: Stream


class MessageUnit(NamedTuple):
    messages: list[Message]
    stream: Stream


SourceQueue = asyncio.Queue[Source]
TextQueue = asyncio.Queue[TextUnit]
PostsQueue = asyncio.Queue[PostsUnit]
MessagesQueue = asyncio.Queue[MessageUnit]


async def main():
    source_queue: SourceQueue = asyncio.Queue()
    text_queue: TextQueue = asyncio.Queue()
    post_queue: PostsQueue = asyncio.Queue()
    messages_queue: MessagesQueue = asyncio.Queue()

    await asyncio.gather(
        _enqueue_sources(source_queue),
        _process_sources(source_queue, text_queue),
        _process_text(text_queue, post_queue),
        _process_posts(post_queue, messages_queue),
        _send_messages(messages_queue),
    )


async def _enqueue_sources(source_queue: SourceQueue):
    path = Path(__file__).parent.parent / "config"
    sources = load_configuration(path)
    for source in sources:
        await source_queue.put(source)


async def _process_sources(source_queue: SourceQueue, text_queue: TextQueue):
    while source := await source_queue.get():
        text = await fetch_text(source)
        await text_queue.put(TextUnit(text=text, source=source))


async def _process_text(text_queue: TextQueue, post_queue: PostsQueue):
    while text_unit := await text_queue.get():
        parsed_posts = await parse_posts(text_unit.source, text_unit.text)
        for stream, posts in parsed_posts:
            await post_queue.put(PostsUnit(posts=posts, stream=stream))


async def _process_posts(post_queue: PostsQueue, messages_queue: MessagesQueue):
    while posts_unit := await post_queue.get():
        messages = await parse_messages_from_posts(posts_unit.posts, posts_unit.stream)
        await messages_queue.put(
            MessageUnit(messages=messages, stream=posts_unit.stream)
        )


async def _send_messages(messages_queue: MessagesQueue):
    while message_unit := await messages_queue.get():
        await send_messages(message_unit.messages, message_unit.stream)


if __name__ == "__main__":
    asyncio.run(main())

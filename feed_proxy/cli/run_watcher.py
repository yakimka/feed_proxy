from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, TypeAlias

from feed_proxy.configuration import load_configuration
from feed_proxy.logic import (
    fetch_text,
    parse_message_batches_from_posts,
    parse_posts,
    send_messages,
)
from feed_proxy.storage import (
    MemoryMessagesOutbox,
    MemoryPostStorage,
    MessagesOutbox,
    OutboxItem,
    PostStorage,
)

if TYPE_CHECKING:
    from feed_proxy.entities import Message, Post, Source, Stream


class TextUnit(NamedTuple):
    text: str
    source: Source


class PostsUnit(NamedTuple):
    posts: list[Post]
    source: Source
    stream: Stream


class MessageUnit(NamedTuple):
    messages: list[Message]
    stream: Stream


SourceQueue: TypeAlias = asyncio.Queue["Source"]
TextQueue: TypeAlias = asyncio.Queue[TextUnit]
PostsQueue: TypeAlias = asyncio.Queue[PostsUnit]
MessagesQueue: TypeAlias = asyncio.Queue[MessageUnit]


async def main():
    logging.basicConfig(level=logging.INFO)
    source_queue: SourceQueue = asyncio.Queue()
    text_queue: TextQueue = asyncio.Queue()
    post_queue: PostsQueue = asyncio.Queue()
    outbox_queue = MemoryMessagesOutbox()
    post_storage = MemoryPostStorage()

    await asyncio.gather(
        _enqueue_sources(source_queue),
        *[_process_sources(i, source_queue, text_queue) for i in range(1, 10)],
        _process_text(text_queue, post_queue),
        _process_posts(post_queue, outbox_queue, post_storage),
        _send_messages(outbox_queue),
    )


async def _enqueue_sources(source_queue: SourceQueue):
    while True:
        path = Path(__file__).parent.parent.parent / "config"
        sources = load_configuration(path)
        for source in sources:
            await source_queue.put(source)
        await asyncio.sleep(60 * 30)


async def _process_sources(i: int, source_queue: SourceQueue, text_queue: TextQueue):
    while source := await source_queue.get():
        logging.info("Worker %s processing %s (fetch_text)", i, source.id)
        text = await fetch_text(source)
        await text_queue.put(TextUnit(text=text, source=source))
        source_queue.task_done()


async def _process_text(text_queue: TextQueue, post_queue: PostsQueue):
    while text_unit := await text_queue.get():
        parsed_posts = await parse_posts(text_unit.source, text_unit.text)
        for stream, posts in parsed_posts:
            await post_queue.put(
                PostsUnit(posts=posts, source=text_unit.source, stream=stream)
            )
        text_queue.task_done()


async def _process_posts(
    post_queue: PostsQueue, outbox_queue: MessagesOutbox, post_storage: PostStorage
):
    while posts_unit := await post_queue.get():
        message_batches = await parse_message_batches_from_posts(
            posts_unit.posts,
            posts_unit.source,
            posts_unit.stream,
            post_storage=post_storage,
        )
        for batch in message_batches:
            await outbox_queue.put(
                OutboxItem(
                    id=uuid.uuid4().hex, messages=batch, stream=posts_unit.stream
                )
            )
        post_queue.task_done()


async def _send_messages(outbox_queue: MessagesOutbox):
    while outbox_item := await outbox_queue.get():
        await send_messages(outbox_item.messages, outbox_item.stream)
        await outbox_queue.commit(outbox_item.id)


if __name__ == "__main__":
    asyncio.run(main())

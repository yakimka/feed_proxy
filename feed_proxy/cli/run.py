from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, TypeAlias

from picodi import Provide, inject
from picodi.helpers import lifespan

from feed_proxy.configuration import read_configuration_from_folder
from feed_proxy.deps import get_metrics, get_outbox_queue, get_post_storage
from feed_proxy.logic import (
    fetch_text,
    parse_message_batches_from_posts,
    parse_posts,
    send_messages,
)
from feed_proxy.observability import Metrics, setup_logging_instruments
from feed_proxy.storage import OutboxItem, PostStorage

if TYPE_CHECKING:
    from feed_proxy.entities import Message, Post, Source, Stream
    from feed_proxy.messages_outbox import MessagesOutbox


logger = logging.getLogger(__name__)


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


@lifespan
@inject
async def worker(
    sources: list[Source],
    metrics: Metrics = Provide(get_metrics),
    post_storage: PostStorage = Provide(get_post_storage),
    outbox_queue: MessagesOutbox = Provide(get_outbox_queue),
) -> None:
    metrics.run_write_to_file_daemon()

    source_queue: SourceQueue = asyncio.Queue()
    text_queue: TextQueue = asyncio.Queue()
    post_queue: PostsQueue = asyncio.Queue()

    await asyncio.gather(
        _enqueue_sources(source_queue, sources),
        *[_fetch_sources(i, source_queue, text_queue, metrics) for i in range(1, 10)],
        _parse_posts_from_text(text_queue, post_queue, metrics),
        _prepare_messages(post_queue, outbox_queue, post_storage, metrics),
        _send_messages(outbox_queue, metrics),
    )


async def _enqueue_sources(source_queue: SourceQueue, sources: list[Source]) -> None:
    while True:
        for source in sources:
            await source_queue.put(source)
        logger.info("Enqueued %s sources, waiting for 30 minutes", len(sources))
        await asyncio.sleep(60 * 30)


async def _fetch_sources(
    job_id: int, source_queue: SourceQueue, text_queue: TextQueue, metrics: Metrics
) -> None:
    while source := await source_queue.get():
        logger.info("Worker %s processing %s (fetch_text)", job_id, source.id)
        text = await fetch_text(source)
        if not text:
            logger.warning("Can't fetch text for %s", source.id)
            metrics.increment_sources_fetched(source.id, "failed")
            continue

        metrics.increment_sources_fetched(source.id, "ok")

        await text_queue.put(TextUnit(text=text, source=source))
        source_queue.task_done()


async def _parse_posts_from_text(
    text_queue: TextQueue, post_queue: PostsQueue, metrics: Metrics
) -> None:
    while text_unit := await text_queue.get():
        logger.info("Processing text for %s (parse_posts)", text_unit.source.id)
        parsed_posts = await parse_posts(text_unit.source, text_unit.text)

        if parsed_posts:
            metrics.increment_posts_parsed(text_unit.source.id)

        for stream, posts in parsed_posts:
            await post_queue.put(
                PostsUnit(posts=posts, source=text_unit.source, stream=stream)
            )
        text_queue.task_done()


async def _prepare_messages(
    post_queue: PostsQueue,
    outbox_queue: MessagesOutbox,
    post_storage: PostStorage,
    metrics: Metrics,
) -> None:
    while posts_unit := await post_queue.get():
        message_batches = await parse_message_batches_from_posts(
            posts_unit.posts,
            posts_unit.source,
            posts_unit.stream,
            post_storage=post_storage,
        )

        for batch in message_batches:
            metrics.increment_messages_prepared(
                posts_unit.source.id, posts_unit.stream.receiver_type, len(batch)
            )

        for batch in message_batches:
            await outbox_queue.put(
                OutboxItem(
                    id=uuid.uuid4().hex,
                    messages=batch,
                    source_id=posts_unit.source.id,
                    stream=posts_unit.stream,
                )
            )
        post_queue.task_done()


async def _send_messages(outbox_queue: MessagesOutbox, metrics: Metrics) -> None:
    while outbox_item := await outbox_queue.get():
        await send_messages(outbox_item.messages, outbox_item.stream)
        await outbox_queue.commit(outbox_item.id)

        metrics.increment_messages_sent(
            outbox_item.source_id,
            outbox_item.stream.receiver_type,
            len(outbox_item.messages),
        )


def main(args: argparse.Namespace) -> None:
    conf = read_configuration_from_folder(Path(args.config))
    setup_logging_instruments(conf.app_settings)
    asyncio.run(worker(conf.sources))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="config")
    args = parser.parse_args()
    main(args)

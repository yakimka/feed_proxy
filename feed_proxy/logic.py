from __future__ import annotations

import asyncio
import copy
import logging
from typing import TYPE_CHECKING

import httpx

from feed_proxy.entities import Message, Modifier, Post, Source, Stream
from feed_proxy.handlers import HandlerType, get_handler_by_name
from feed_proxy.utils.http import ACCEPT_HEADER, DEFAULT_UA

if TYPE_CHECKING:
    from feed_proxy.storage import PostStorage

logger = logging.getLogger(__name__)


async def fetch_text(source: Source) -> str:
    fetcher = get_handler_by_name(
        type=HandlerType.fetchers,
        name=source.fetcher_type,
        options=source.fetcher_options,
    )
    return await fetcher()


async def parse_posts(source: Source, text: str) -> list[tuple[Stream, list[Post]]]:
    parser = get_handler_by_name(
        name=source.parser_type,
        type=HandlerType.parsers,
        options=source.parser_options,
    )
    posts = await parser(text)
    result = []
    for stream in source.streams:
        stream_posts = copy.deepcopy(posts)
        for post in stream_posts:
            post.source_tags = source.tags
        stream_posts = await apply_modifiers_to_posts(stream.modifiers, stream_posts)
        result.append((stream, stream_posts))
    return result


async def apply_modifiers_to_posts(
    modifiers: list[Modifier], posts: list[Post]
) -> list[Post]:
    for modifier in modifiers:
        modifier_func = get_handler_by_name(
            name=modifier.type,
            type=HandlerType.modifiers,
            options=modifier.options,
        )
        posts = await modifier_func(posts)
    return posts


async def parse_message_batches_from_posts(
    posts: list[Post], source: Source, stream: Stream, post_storage: PostStorage
) -> list[list[Message]]:
    message_batches: list[list[Message]] = []
    key = (source.id, stream.receiver_type)
    if not await post_storage.has_posts(key):
        logger.info("First run for %s, skipping all posts", key)
        all_posts = [post.post_id for post in posts]
        await post_storage.mark_posts_as_processed(key, all_posts)
        return message_batches

    messages = []
    to_mark = []
    for post in reversed(posts):
        if await post_storage.is_post_processed(key, post.post_id):
            continue
        assert stream.message_template, "Stream message template is not set"
        messages.append(
            Message(
                post_id=post.post_id,
                template=stream.message_template,
                template_kwargs=post.template_kwargs(),
            )
        )
        logger.info("New post %s for %s", post, key)
        to_mark.append(post.post_id)
    await post_storage.mark_posts_as_processed(key, to_mark)

    if not messages:
        logger.info("No new posts for %s", key)
        return message_batches

    if stream.squash:
        message_batches.append(messages)
    else:
        message_batches.extend([message] for message in messages)
    return message_batches


async def send_messages(messages: list[Message], stream: Stream) -> None:
    receiver = get_handler_by_name(
        name=stream.receiver_type,
        type=HandlerType.receivers,
        options=stream.receiver_options,
    )
    await receiver(messages)


async def fetch_text_from_url(
    url: str, *, encoding: str = "", retry: int = 0
) -> str | None:
    # TODO don't fetch if content is not changed
    async with httpx.AsyncClient(
        follow_redirects=True, verify=False, timeout=30  # noqa: S501
    ) as client:
        while True:
            res_text = None
            try:
                res = await client.get(
                    url,
                    headers={
                        "user-agent": DEFAULT_UA,
                        "accept": ACCEPT_HEADER,
                        "accept-language": "uk-UA,uk;q=0.8,en-US;q=0.5,en;q=0.3",
                    },
                    timeout=30.0,
                )
                res_text = res.text
                res.raise_for_status()
            except httpx.HTTPError as e:
                if retry > 0:
                    msg = (
                        f"Failed to fetch {url} with {e} and {retry} retries"
                        " left. Retrying..."
                    )
                    logger.warning(msg)
                    retry -= 1
                    await asyncio.sleep(3.0)
                    continue

                logger.warning(
                    "Error while fetching %s: error %s\n%s",
                    url,
                    type(e).__name__,
                    res_text,
                )
                return None

            if encoding:
                res.encoding = encoding

            return res.text

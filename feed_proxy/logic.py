import asyncio
import copy

import httpx

from feed_proxy.entities import Message, Modifier, Post, Source, Stream
from feed_proxy.handlers import HandlerType, get_handler_by_name
from feed_proxy.sentry.error_tracking import write_warn_message
from feed_proxy.utils.http import DEFAULT_UA, logger


async def fetch_text(source: Source) -> str:
    fetcher = get_handler_by_name(
        type=HandlerType.fetchers.value,
        name=source.fetcher_type,
        options=source.fetcher_options,
    )
    return await fetcher()


async def parse_posts(source: Source, text: str) -> list[tuple[Stream, list[Post]]]:
    parser = get_handler_by_name(
        name=source.parser_type,
        type=HandlerType.parsers.value,
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
            type=HandlerType.modifiers.value,
            options=modifier.options,
        )
        posts = await modifier_func(posts)
    return posts


async def parse_messages_from_posts(posts: list[Post], stream: Stream) -> list[Message]:
    messages = []
    for post in posts:
        message = Message(
            post_id=post.post_id,
            template=stream.message_template,
            template_kwargs=post.template_kwargs(),
        )
        messages.append(message)
    return messages


async def send_messages(messages: list[Message], stream: Stream):
    receiver = get_handler_by_name(
        name=stream.receiver.type,
        type=HandlerType.receivers.value,
        options={
            **stream.receiver.options,
            **stream.receiver_options,
        },
    )
    await receiver(messages)


async def fetch_text_from_url(url: str, *, encoding="", retry=0) -> str | None:
    # TODO don't fetch if content is not changed
    async with httpx.AsyncClient(
        follow_redirects=True, verify=False, timeout=30  # noqa: S501
    ) as client:
        while True:
            try:
                res = await client.get(
                    url, headers={"user-agent": DEFAULT_UA}, timeout=30.0
                )
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

                msg = f"Error while fetching {url}: error {type(e).__name__}\n{e}"
                write_warn_message(msg, logger.warning)
                return None

            if encoding:
                res.encoding = encoding

            return res.text

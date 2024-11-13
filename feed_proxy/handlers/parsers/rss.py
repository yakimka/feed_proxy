import asyncio
import dataclasses
import json
import logging
from typing import Any

import feedparser

from feed_proxy.entities import Post
from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler
from feed_proxy.utils.text import make_hash_tags

logger = logging.getLogger(__name__)


@dataclasses.dataclass()
class FeedPost(Post):
    post_id: str
    title: str
    url: str
    comments_url: str
    post_tags: tuple | list
    source_tags: tuple | list

    def __str__(self) -> str:
        return self.title

    def template_kwargs(self) -> dict[str, Any]:
        return {
            "post_id": self.post_id,
            "title": self.title,
            "url": self.url,
            "comments_url": self.comments_url,
            "post_tags": "; ".join(self.post_tags),
            "source_tags": "; ".join(self.source_tags),
            "post_hash_tags": " ".join(make_hash_tags(self.post_tags)),
            "source_hash_tags": " ".join(make_hash_tags(self.source_tags)),
        }


@register_handler(
    type=HandlerType.parsers,
    return_model=FeedPost,
)
async def rss(
    text: str, *, options: HandlerOptions | None = None  # noqa: U100
) -> list[FeedPost]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _handler, text)


def _handler(text: str) -> list[FeedPost]:
    posts: list[FeedPost] = []

    if not text:
        return posts

    def get_tags(entry: dict) -> tuple[str, ...]:
        return tuple(tag.term for tag in entry.get("tags", []))

    feed = feedparser.parse(
        text, response_headers={"content-type": "text/html; charset=utf-8"}
    )
    for entry in feed["entries"]:
        try:
            id_field = entry.keymap["guid"]
            posts.append(
                FeedPost(
                    post_id=entry.get(id_field) or _clean_post_id(entry.link),
                    title=entry.title,
                    url=entry.get("link"),
                    comments_url=entry.get("comments"),
                    post_tags=get_tags(entry),
                    source_tags=[],
                ),
            )
        except Exception:  # noqa: PIE786
            entry = json.dumps(entry, sort_keys=True, indent=4)
            logger.exception("Failed to parse entry: %s", entry)

    return posts


def _clean_post_id(post_id: str) -> str:
    return post_id.removeprefix("https://").removeprefix("http://")

import dataclasses
import html
import json
import logging
from typing import Any

from feed_proxy.entities import Post
from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler
from feed_proxy.utils.text import make_hash_tags

logger = logging.getLogger(__name__)


@dataclasses.dataclass()
class WordpressPost(Post):
    post_id: str
    title: str
    url: str
    source_tags: tuple | list
    description: str = ""
    content: str = ""
    extras: dict[str, str] = dataclasses.field(default_factory=dict)

    def __str__(self) -> str:
        return self.title

    def template_kwargs(self) -> dict[str, Any]:
        base = {
            "post_id": self.post_id,
            "title": self.title,
            "url": self.url,
            "source_tags": "; ".join(self.source_tags),
            "source_hash_tags": " ".join(make_hash_tags(self.source_tags)),
            "description": self.description,
            "content": self.content,
        }
        return {**base, **self.extras}


@register_handler(
    type=HandlerType.parsers,
    return_model=WordpressPost,
)
async def wordpress(
    text: str, *, options: HandlerOptions | None = None  # noqa: U100
) -> list[WordpressPost]:
    raw = json.loads(text)

    if not isinstance(raw, list):
        logger.warning("Unexpected WordPress API response, expected a list: %s", raw)
        return []

    return [
        WordpressPost(
            post_id=str(entry["id"]),
            title=html.unescape(entry["title"]["rendered"]),
            url=entry["link"],
            source_tags=[],
            description=entry["excerpt"]["rendered"],
            content=entry["content"]["rendered"],
        )
        for entry in raw
    ]

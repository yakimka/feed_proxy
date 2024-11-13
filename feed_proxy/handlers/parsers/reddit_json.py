import dataclasses
import json
import logging
from typing import Any

from feed_proxy.entities import Post
from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler
from feed_proxy.utils.text import make_hash_tags

logger = logging.getLogger(__name__)


@dataclasses.dataclass()
class RedditPost(Post):
    post_id: str
    title: str
    url: str
    comments: str
    score: int
    source_tags: tuple | list

    def __str__(self) -> str:
        return self.title

    def template_kwargs(self) -> dict[str, Any]:
        return {
            "post_id": self.post_id,
            "title": self.title,
            "url": self.url,
            "comments": self.comments,
            "score": self.score,
            "source_tags": "; ".join(self.source_tags),
            "source_hash_tags": " ".join(make_hash_tags(self.source_tags)),
        }

    @classmethod
    def fields_schema(cls) -> dict:
        return {
            "post_id": {"type": "string"},
            "title": {"type": "string"},
            "url": {"type": "string"},
            "comments": {"type": "string"},
            "score": {"type": "integer"},
            "source_tags": {"type": "array"},
            "source_hash_tags": {"only_template": True},
        }


@register_handler(
    type=HandlerType.parsers,
    return_fields_schema=RedditPost.fields_schema(),
    return_model=RedditPost,
)
async def reddit_json(
    text: str, *, options: HandlerOptions | None = None  # noqa: U100
) -> list[RedditPost]:
    raw_post = json.loads(text)
    return [
        RedditPost(
            post_id=entry["data"]["id"],
            title=entry["data"]["title"],
            url=entry["data"]["url"],
            comments=f"https://reddit.com{entry['data']['permalink']}",
            score=entry["data"]["score"],
            source_tags=[],
        )
        for entry in raw_post["data"]["children"]
    ]

import dataclasses
import logging

from feed_proxy.entities import Post
from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ReplaceTestOptions(HandlerOptions):
    DESCRIPTIONS = {
        "field": ("Field", "Field name"),
        "old": ("Old value", "Value to replace"),
        "new": ("New value", "Value to replace with"),
    }

    field: str
    old: str
    new: str


@register_handler(
    type=HandlerType.modifiers.value,
    options=ReplaceTestOptions,
)
async def replace_text(posts: list[Post], *, options: ReplaceTestOptions) -> list[Post]:
    def replace_text_in_post(post: Post) -> Post:
        value = getattr(post, options.field)
        value = value.replace(options.old, options.new)
        setattr(post, options.field, value)
        return post

    return [replace_text_in_post(post) for post in posts]

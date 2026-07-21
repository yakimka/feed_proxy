from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler

if TYPE_CHECKING:
    from feed_proxy.entities import Post


@dataclasses.dataclass
class StripHtmlOptions(HandlerOptions):
    DESCRIPTIONS = {
        "field": ("Field", "Field name"),
        "separator": ("Separator", "String inserted between text from adjacent tags"),
    }

    field: str
    separator: str = " "


@register_handler(
    type=HandlerType.modifiers,
    options=StripHtmlOptions,
)
async def strip_html(posts: list[Post], *, options: StripHtmlOptions) -> list[Post]:
    def strip_in_post(post: Post) -> Post:
        value = getattr(post, options.field) or ""
        text = BeautifulSoup(value, "lxml").get_text(separator=options.separator)
        setattr(post, options.field, text.strip())
        return post

    return [strip_in_post(post) for post in posts]

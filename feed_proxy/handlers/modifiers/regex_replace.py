from __future__ import annotations

import dataclasses
import re
from typing import TYPE_CHECKING

from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler

if TYPE_CHECKING:
    from feed_proxy.entities import Post


@dataclasses.dataclass
class RegexReplaceOptions(HandlerOptions):
    DESCRIPTIONS = {
        "field": ("Field", "Field name"),
        "pattern": ("Pattern", "Regular expression to search for"),
        "replacement": ("Replacement", "Replacement string (supports \\1 group refs)"),
        "dotall": ("Dot matches newline", "Let '.' in the pattern match newlines too"),
    }

    field: str
    pattern: str
    replacement: str = ""
    dotall: bool = False


@register_handler(
    type=HandlerType.modifiers,
    options=RegexReplaceOptions,
)
async def regex_replace(
    posts: list[Post], *, options: RegexReplaceOptions
) -> list[Post]:
    compiled = re.compile(options.pattern, re.DOTALL if options.dotall else 0)

    def replace_in_post(post: Post) -> Post:
        value = getattr(post, options.field) or ""
        setattr(post, options.field, compiled.sub(options.replacement, value))
        return post

    return [replace_in_post(post) for post in posts]

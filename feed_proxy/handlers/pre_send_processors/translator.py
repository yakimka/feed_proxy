from __future__ import annotations

import dataclasses
import logging
import os
from typing import TYPE_CHECKING

from google import genai

from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler

if TYPE_CHECKING:
    from feed_proxy.entities import Post

logger = logging.getLogger(__name__)

_client: genai.Client | None = None

_PROMPT_TEMPLATE = (
    "Translate the following text to {language}. Output only the translation, "
    "no explanations.\n\nText:\n{source}"
)


@dataclasses.dataclass
class TranslatorOptions(HandlerOptions):
    DESCRIPTIONS = {
        "source_field": ("Source field", "Post field or extras key to translate"),
        "target_field": ("Target field", "Extras key to write the translation to"),
        "target_language": ("Target language", "Language to translate the text to"),
        "model": ("Model", "Gemini model to use"),
        "on_error_value": (
            "On error value",
            "Value written to target field if translation fails",
        ),
    }

    source_field: str
    target_field: str
    target_language: str
    model: str = "gemini-2.0-flash"
    on_error_value: str = "[translation failed]"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _read_field(post: Post, name: str) -> str:
    extras = getattr(post, "extras", {})
    if name in extras:
        return extras[name]
    return getattr(post, name, "") or ""


async def _translate(source: str, language: str, model: str) -> str:
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=model,
        contents=_PROMPT_TEMPLATE.format(language=language, source=source),
    )
    return response.text or ""


@register_handler(
    type=HandlerType.pre_send_processors,
    options=TranslatorOptions,
)
async def translator(posts: list[Post], *, options: TranslatorOptions) -> list[Post]:
    for post in posts:
        source = _read_field(post, options.source_field)
        if not source:
            continue
        try:
            translation = await _translate(
                source, options.target_language, options.model
            )
        except Exception:  # noqa: PIE786
            logger.exception(
                "Failed to translate field %s for post %s", options.source_field, post
            )
            translation = options.on_error_value
        extras: dict[str, str] = getattr(post, "extras", {})
        extras[options.target_field] = translation

    return posts

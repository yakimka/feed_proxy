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

_MODEL = "gemini-3.5-flash"

_client: genai.Client | None = None


@dataclasses.dataclass
class LlmPromptOptions(HandlerOptions):
    DESCRIPTIONS = {
        "source_field": ("Source field", "Post field or extras key to read text from"),
        "target_field": ("Target field", "Extras key to write the result to"),
        "prompt": (
            "Prompt",
            "Instruction for the model; must contain the {source} placeholder, "
            "which is replaced with the source text",
        ),
        "on_error_value": (
            "On error value",
            "Value written to target field on failure; defaults to the "
            "unprocessed source text",
        ),
    }

    source_field: str
    target_field: str
    prompt: str
    on_error_value: str | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options=genai.types.HttpOptions(timeout=30_000),
        )
    return _client


def _read_field(post: Post, name: str) -> str:
    extras = getattr(post, "extras", {})
    if name in extras:
        return extras[name]
    return getattr(post, name, "") or ""


async def _run_prompt(prompt: str, source: str) -> str:
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=_MODEL,
        contents=prompt.replace("{source}", source),
    )
    if not response.text:
        raise ValueError("Empty response from model")
    return response.text


@register_handler(
    type=HandlerType.pre_send_processors,
    options=LlmPromptOptions,
)
async def llm_prompt(posts: list[Post], *, options: LlmPromptOptions) -> list[Post]:
    for post in posts:
        source = _read_field(post, options.source_field)
        extras: dict[str, str] = getattr(post, "extras", {})
        if not source:
            extras[options.target_field] = source
            continue
        try:
            result = await _run_prompt(options.prompt, source)
        except Exception:  # noqa: PIE786
            logger.exception(
                "Failed to run llm_prompt for field %s of post %s",
                options.source_field,
                post,
            )
            result = (
                options.on_error_value if options.on_error_value is not None else source
            )
        extras[options.target_field] = result

    return posts

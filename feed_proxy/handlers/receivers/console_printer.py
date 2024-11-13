from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from feed_proxy.handlers import HandlerType, register_handler
from feed_proxy.utils.text import template_to_text

if TYPE_CHECKING:
    from feed_proxy.handlers.types import Message

logger = logging.getLogger(__name__)


@register_handler(
    type=HandlerType.receivers,
    options=None,
)
async def console_printer(messages: list[Message]) -> None:
    if not messages:
        return
    parts: list[str] = []
    delimiter = "\n-----\n"
    for message in messages:
        parts.append(template_to_text(message.template, **message.template_kwargs))
        parts.append(delimiter)
    if parts:
        parts.pop()

    print("".join(parts))


@register_handler(
    type=HandlerType.receivers,
    name="named_console_printer",
    options=None,
)
class NamedConsolePrinter:
    def __init__(self, name: str):
        print(f"NamedConsolePrinter(name={name}).__init__")
        self._name = name

    async def __call__(self, messages: list[Message]) -> None:
        await console_printer(messages)

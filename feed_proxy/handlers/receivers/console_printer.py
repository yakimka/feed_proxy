import logging
from functools import lru_cache
from typing import Protocol

from aiogram import Bot

from feed_proxy.handlers import HandlerType, register_handler
from feed_proxy.utils.text import template_to_text

logger = logging.getLogger(__name__)


class Message(Protocol):
    text: str
    template: str
    template_kwargs: dict


@lru_cache(maxsize=128)
def _get_bot(token: str) -> Bot:
    return Bot(token=token)


@register_handler(
    type=HandlerType.receivers.value,
    name="console_printer",
    options=None,
)
class ConsolePrinter:
    def __init__(self, name: str):
        print("ConsolePrinter.__init__")
        self._name = name

    def _lock_key(self, *_, **__):
        return self._name

    async def __call__(
        self,
        messages: list[Message],
    ) -> None:
        if not messages:
            return
        parts: list[str] = []
        delimiter = "\n-----\n"
        for message in messages:
            parts.extend(
                (
                    template_to_text(message.template, **message.template_kwargs),
                    delimiter,
                )
            )
        if parts:
            parts.pop()

        print("".join(parts))

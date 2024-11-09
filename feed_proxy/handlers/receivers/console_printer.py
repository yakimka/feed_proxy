import dataclasses
import logging
from functools import lru_cache
from typing import Protocol

from aiogram import Bot

from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler
from feed_proxy.text import template_to_text

logger = logging.getLogger(__name__)


class Message(Protocol):
    text: str
    template: str
    template_kwargs: dict


@dataclasses.dataclass
class ConsolePrinterOptions(HandlerOptions):
    DESCRIPTIONS = {
        "chat_id": ("Chat ID", "Telegram chat id"),
        "disable_link_preview": ("Disable link preview", ""),
    }

    chat_id: str
    disable_link_preview: bool = False


@lru_cache(maxsize=128)
def _get_bot(token: str) -> Bot:
    return Bot(token=token)


@register_handler(
    type=HandlerType.receivers.value,
    name="console_printer",
    options=ConsolePrinterOptions,
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
        *,
        options: ConsolePrinterOptions,
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

        text = "".join(parts)
        await self._send_message(message=text)

    # @async_lock(key=_lock_key, wait_time=pause_between_send)
    async def _send_message(self, message: str) -> None:
        print(message)
        logger.info("Sent message to %s", self._name)

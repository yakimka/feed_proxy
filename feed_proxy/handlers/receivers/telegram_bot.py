import dataclasses
import html
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
class TelegramBotOptions(HandlerOptions):
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
    name="telegram_bot",
    options=TelegramBotOptions,
)
class TelegramBot:
    MAX_MESSAGE_LENGTH = 4096
    MAX_MESSAGES_PER_MINUTE_PER_GROUP = 20
    pause_between_send = 60 / MAX_MESSAGES_PER_MINUTE_PER_GROUP  # seconds

    def __init__(self, name: str, token: str):
        self._name = name
        self.bot = _get_bot(token)

    def _lock_key(self, *_, **__):
        return self._name

    async def __call__(
        self,
        messages: list[Message],
        *,
        options: TelegramBotOptions,
    ) -> None:
        if not messages:
            return
        parts: list[str] = []
        delimiter = "\n-----\n"
        for message in messages:
            parts.extend((_from_message_to_text(message), delimiter))
        if parts:
            parts.pop()

        added_truncated_message = False
        while sum(len(part) for part in parts) > self.MAX_MESSAGE_LENGTH:
            if not added_truncated_message:
                parts.append("\nTruncated...")
                added_truncated_message = True
            parts.pop(-2)

        text = "".join(parts)
        await self._send_message(
            message=text,
            chat_id=options.chat_id,
            disable_link_preview=options.disable_link_preview,
        )

    # @async_lock(key=_lock_key, wait_time=pause_between_send)
    async def _send_message(
        self, message: str, chat_id: str, disable_link_preview: bool
    ) -> None:
        await self.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=disable_link_preview,
        )
        logger.info("Sent message to %s (%s)", self._name, chat_id)


def _from_message_to_text(message: Message) -> str:
    text = message.text
    if message.template:
        template_kwargs = _html_escape_kwargs(message.template_kwargs)
        text = template_to_text(message.template, **template_kwargs)

    return text.strip()


def _html_escape_kwargs(template_kwargs: dict) -> dict[str, str]:
    return {
        key: html.escape(value) if value else value
        for key, value in template_kwargs.items()
    }

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from feed_proxy.entities import Message, Stream


class Stringable(Protocol):
    def __str__(self) -> str:
        pass


class PostStorage(Protocol):
    async def has_posts(self, key: Stringable) -> bool:
        pass

    async def is_post_processed(self, key: Stringable, post_id: str) -> bool:
        pass

    async def mark_posts_as_processed(
        self, key: Stringable, post_ids: list[str]
    ) -> None:
        pass


class MemoryPostStorage:
    def __init__(self) -> None:
        self._data: dict[str, set[str]] = {}

    async def has_posts(self, key: Stringable) -> bool:
        return bool(self._data.get(str(key)))

    async def is_post_processed(self, key: Stringable, post_id: str) -> bool:
        return post_id in self._data.get(str(key), set())

    async def mark_posts_as_processed(
        self, key: Stringable, post_ids: list[str]
    ) -> None:
        self._data.setdefault(str(key), set()).update(post_ids)


@dataclass
class OutboxItem:
    id: str
    messages: list[Message]
    stream: Stream


class MessagesOutbox(Protocol):
    async def put(self, item: OutboxItem) -> None:
        pass

    async def get(self) -> OutboxItem:
        pass

    async def commit(self, id: str) -> None:
        pass


class MemoryMessagesOutbox:
    def __init__(self) -> None:
        self._queue: list[OutboxItem] = []

    async def put(self, item: OutboxItem) -> None:
        self._queue.append(item)

    async def get(self) -> OutboxItem:
        while True:
            if not self._queue:
                await asyncio.sleep(0.1)
            else:
                return self._queue[0]

    async def commit(self, id: str) -> None:
        for i, queue_item in enumerate(self._queue):
            if queue_item.id == id:
                self._queue.pop(i)
                break

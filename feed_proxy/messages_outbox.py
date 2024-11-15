from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feed_proxy.storage import MessagesOutboxStorage, OutboxItem


def current_timestamp() -> int:
    return int(time.time())


class MessagesOutbox:
    def __init__(
        self,
        storage: MessagesOutboxStorage,
        current_timestamp_func: Callable[[], int] = current_timestamp,
    ) -> None:
        self._storage = storage
        self._dead_letter_delta = 60 * 10
        self._current_timestamp_func = current_timestamp_func

    async def put(self, item: OutboxItem) -> None:
        return await self._storage.put(item)

    async def get(self) -> OutboxItem:
        while True:
            item = await self._storage.get(self._current_timestamp_func())
            if item is not None:
                return item
            await asyncio.sleep(0.1)

    async def get_dead_letter(self) -> OutboxItem:
        while True:
            item = await self._storage.get_dead_letter(
                self._current_timestamp_func(), self._dead_letter_delta
            )
            if item is not None:
                return item
            await asyncio.sleep(10)

    async def commit(self, id: str) -> None:
        await self._storage.commit(id)

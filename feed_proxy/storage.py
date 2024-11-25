from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol

from dacite import from_dict

from feed_proxy.entities import Message, Stream  # noqa: TC001


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


class SqlitePostStorage:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    async def has_posts(self, key: Stringable) -> bool:
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM posts WHERE key = ?", (str(key),))
        return bool(cursor.fetchone()[0])

    async def is_post_processed(self, key: Stringable, post_id: str) -> bool:
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM posts WHERE key = ? AND post_id = ?",
            (str(key), post_id),
        )
        return bool(cursor.fetchone()[0])

    async def mark_posts_as_processed(
        self, key: Stringable, post_ids: list[str]
    ) -> None:
        cursor = self._conn.cursor()
        cursor.executemany(
            "INSERT INTO posts (key, post_id) VALUES (?, ?)",
            [(str(key), post_id) for post_id in post_ids],
        )
        self._conn.commit()


@dataclass
class OutboxItem:
    id: str
    messages: list[Message]
    source_id: str
    stream: Stream


class MessagesOutboxStorage(Protocol):
    async def put(self, item: OutboxItem) -> None:
        pass

    async def get(self, current_timestamp: int) -> OutboxItem | None:
        pass

    async def get_dead_letter(
        self, current_timestamp: int, delta: int
    ) -> OutboxItem | None:
        pass

    async def commit(self, id: str) -> None:
        pass


class MemoryMessagesOutboxStorage:
    def __init__(self) -> None:
        self._queue: list[OutboxItem] = []
        self._in_progress: dict[str, int] = {}

    async def put(self, item: OutboxItem) -> None:
        self._queue.append(item)

    async def get(self, current_timestamp: int) -> OutboxItem | None:
        for item in self._queue:
            if item.id in self._in_progress:
                continue
            self._in_progress[item.id] = current_timestamp
            return item
        return None

    async def get_dead_letter(
        self, current_timestamp: int, delta: int
    ) -> OutboxItem | None:
        in_progress = sorted(self._in_progress.items(), key=lambda x: x[1])
        for item_id, _ in in_progress:
            if current_timestamp - self._in_progress[item_id] >= delta:
                item = next((item for item in self._queue if item.id == item_id), None)
                assert item is not None, f"Item {item_id} not found in the queue"
                return item
            else:
                break
        return None

    async def commit(self, id: str) -> None:
        for i, queue_item in enumerate(self._queue):
            if queue_item.id == id:
                self._queue.pop(i)
                break
        self._in_progress.pop(id, None)


def outbox_item_to_sqlite_serializer(item: OutboxItem) -> tuple[str, str]:
    return (item.id, json.dumps(asdict(item)))


def sqlite_to_outbox_item_deserializer(row: tuple[str, str]) -> OutboxItem:
    return from_dict(OutboxItem, json.loads(row[1]))


class SqliteMessagesOutboxStorage:
    def __init__(
        self,
        conn: sqlite3.Connection,
        serializer: Callable[
            [OutboxItem], tuple[str, str]
        ] = outbox_item_to_sqlite_serializer,
        deserializer: Callable[
            [tuple[str, str]], OutboxItem
        ] = sqlite_to_outbox_item_deserializer,
    ) -> None:
        self._conn = conn
        self._serializer = serializer
        self._deserializer = deserializer

    async def put(self, item: OutboxItem) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO outbox (id, data) VALUES (?, ?)", self._serializer(item)
        )

    async def get(self, current_timestamp: int) -> OutboxItem | None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, data FROM outbox
            WHERE in_progress_at IS NULL
            ORDER BY created_at
            LIMIT 1
            """
        )
        item = cursor.fetchone()
        if not item:
            return None

        # Mark the item as in progress with the current timestamp
        item_id = item[0]
        cursor.execute(
            "UPDATE outbox SET in_progress_at = ? WHERE id = ?",
            (current_timestamp, item_id),
        )
        self._conn.commit()

        return self._deserializer(item)

    async def get_dead_letter(
        self, current_timestamp: int, delta: int
    ) -> OutboxItem | None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, data FROM outbox
            WHERE in_progress_at IS NOT NULL
            AND in_progress_at <= ?
            ORDER BY in_progress_at
            LIMIT 1
            """,
            (current_timestamp - delta,),
        )
        item = cursor.fetchone()
        if not item:
            return None

        return self._deserializer(item)

    async def commit(self, id: str) -> None:
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM outbox WHERE id = ?", (id,))
        self._conn.commit()


def create_sqlite_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            key TEXT NOT NULL,
            post_id TEXT NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS outbox (
            id TEXT NOT NULL,
            data JSON NOT NULL,
            in_progress_at INTEGER,
            created_at INTEGER DEFAULT (strftime('%s', 'now')) NOT NULL
        );
        """
    )
    conn.commit()
    return conn

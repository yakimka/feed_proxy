from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol

from dacite import from_dict

from feed_proxy.entities import Message, Stream  # noqa: TC001


class PostStorage(Protocol):
    async def has_posts(self, source_id: str, receiver_type: str) -> bool:
        pass

    async def any_processed(
        self, dedup_group: str, receiver_type: str, post_ids: list[str]
    ) -> bool:
        pass

    async def mark_posts_as_processed(
        self,
        source_id: str,
        dedup_group: str,
        receiver_type: str,
        post_ids: list[str],
    ) -> None:
        pass


class MemoryPostStorage:
    def __init__(self) -> None:
        self._owner: set[tuple[str, str]] = set()
        self._dedup: dict[tuple[str, str], set[str]] = {}

    async def has_posts(self, source_id: str, receiver_type: str) -> bool:
        return (source_id, receiver_type) in self._owner

    async def any_processed(
        self, dedup_group: str, receiver_type: str, post_ids: list[str]
    ) -> bool:
        if not post_ids:
            return False
        return bool(
            self._dedup.get((dedup_group, receiver_type), set()) & set(post_ids)
        )

    async def mark_posts_as_processed(
        self,
        source_id: str,
        dedup_group: str,
        receiver_type: str,
        post_ids: list[str],
    ) -> None:
        self._owner.add((source_id, receiver_type))
        self._dedup.setdefault((dedup_group, receiver_type), set()).update(post_ids)


class SqlitePostStorage:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    async def has_posts(self, source_id: str, receiver_type: str) -> bool:
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT 1 FROM posts WHERE source_id = ? AND receiver_type = ? LIMIT 1",
            (source_id, receiver_type),
        )
        return cursor.fetchone() is not None

    async def any_processed(
        self, dedup_group: str, receiver_type: str, post_ids: list[str]
    ) -> bool:
        if not post_ids:
            return False
        cursor = self._conn.cursor()
        placeholders = ", ".join("?" for _ in post_ids)
        query = (
            f"SELECT 1 FROM posts WHERE dedup_group = ? "  # noqa: S608
            f"AND receiver_type = ? AND post_id IN ({placeholders}) LIMIT 1"
        )
        cursor.execute(query, (dedup_group, receiver_type, *post_ids))
        return cursor.fetchone() is not None

    async def mark_posts_as_processed(
        self,
        source_id: str,
        dedup_group: str,
        receiver_type: str,
        post_ids: list[str],
    ) -> None:
        cursor = self._conn.cursor()
        cursor.executemany(
            "INSERT INTO posts (source_id, dedup_group, receiver_type, post_id) "
            "VALUES (?, ?, ?, ?)",
            [(source_id, dedup_group, receiver_type, pid) for pid in post_ids],
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
            source_id     TEXT NOT NULL,
            dedup_group   TEXT NOT NULL,
            receiver_type TEXT NOT NULL,
            post_id       TEXT NOT NULL
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

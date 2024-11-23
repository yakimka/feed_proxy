import asyncio

import pytest

from feed_proxy.storage import (
    MemoryMessagesOutboxStorage,
    SqliteMessagesOutboxStorage,
    create_sqlite_conn,
)


@pytest.fixture(params=[MemoryMessagesOutboxStorage, SqliteMessagesOutboxStorage])
def make_sut(request):
    def _make_sut():
        if request.param == SqliteMessagesOutboxStorage:
            conn = create_sqlite_conn(":memory:")
            return SqliteMessagesOutboxStorage(conn)
        elif request.param == MemoryMessagesOutboxStorage:
            return MemoryMessagesOutboxStorage()
        else:
            raise ValueError("Invalid storage type")

    return _make_sut


async def test_can_put_and_get_item(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)

    result = await sut.get(100)

    assert result == item


async def test_one_message_can_be_retrieved_only_once(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)

    first_consume = sut.get(100)
    assert await first_consume == item

    result = await sut.get(100)

    assert result is None


async def test_item_disappears_after_commit(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)
    await sut.commit(item.id)

    result = await sut.get(100)

    assert result is None


async def test_one_message_can_be_retrieved_only_once_even_in_concurrent_requests(
    make_sut, mother
):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)

    results = await asyncio.gather(*[sut.get(100) for _ in range(10)])

    assert len([r for r in results if r == item]) == 1


async def test_can_get_item_from_dead_letter(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)
    await sut.get(100)

    result = await sut.get_dead_letter(101, 1)

    assert result == item


async def test_cant_get_item_from_dead_letter_if_delta_is_too_small(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)
    await sut.get(100)

    result = await sut.get_dead_letter(110, 11)

    assert result is None

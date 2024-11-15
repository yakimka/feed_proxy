import asyncio

import pytest

from feed_proxy.storage import (
    MemoryMessagesOutbox,
    SqliteMessagesOutbox,
    create_sqlite_conn,
)


@pytest.fixture(params=[MemoryMessagesOutbox, SqliteMessagesOutbox])
def make_sut(request):
    def _make_sut():
        if request.param == SqliteMessagesOutbox:
            conn = create_sqlite_conn(":memory:")
            return SqliteMessagesOutbox(conn)
        elif request.param == MemoryMessagesOutbox:
            return MemoryMessagesOutbox()
        else:
            raise ValueError("Invalid storage type")

    return _make_sut


async def test_can_put_and_get_item(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)

    result = await sut.get()

    assert result == item


async def test_get_wait_forever_if_queue_is_empty(make_sut):
    sut = make_sut()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sut.get(), timeout=0.5)


async def test_get_wait_item_until_it_appears(make_sut, mother):
    sut = make_sut()
    item = mother.outbox_item()
    task = asyncio.create_task(sut.get())
    await asyncio.sleep(0.1)

    await sut.put(item)
    result = await task

    assert result == item


async def test_one_message_can_be_retrieved_only_once(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)

    first_consume = asyncio.wait_for(sut.get(), timeout=0.5)
    assert await first_consume == item

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sut.get(), timeout=0.5)


async def test_item_disappears_after_commit(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)
    await sut.commit(item.id)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sut.get(), timeout=0.5)


async def test_one_message_can_be_retrieved_only_once_even_in_concurrent_requests(
    make_sut, mother
):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)

    async def consume():
        try:
            return await asyncio.wait_for(sut.get(), timeout=0.5)
        except asyncio.TimeoutError:
            return None

    results = await asyncio.gather(*[consume() for _ in range(10)])

    assert len([r for r in results if r == item]) == 1

import asyncio

import pytest

from feed_proxy.storage import MemoryMessagesOutbox


@pytest.fixture()
def make_sut():
    def _make_sut():
        return MemoryMessagesOutbox()

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


async def test_can_get_item_multiple_times_if_it_not_commited(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)

    results = [await asyncio.wait_for(sut.get(), timeout=0.5) for _ in range(3)]

    assert all(result == item for result in results)


async def test_item_disappears_after_commit(make_sut, mother):
    sut = make_sut()

    item = mother.outbox_item()
    await sut.put(item)
    await sut.commit(item.id)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sut.get(), timeout=0.5)

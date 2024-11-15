import pytest

from feed_proxy.storage import MemoryPostStorage


@pytest.fixture()
def make_sut():
    def _make_sut():
        return MemoryPostStorage()

    return _make_sut


async def test_can_mark_posts_as_processed_and_check_it(make_sut):
    sut = make_sut()

    assert not await sut.has_posts("key")
    assert not await sut.is_post_processed("key", "mypost")

    await sut.mark_posts_as_processed("key", ["mypost"])

    assert await sut.has_posts("key")
    assert await sut.is_post_processed("key", "mypost")


async def test_has_posts_operate_only_on_passed_key(make_sut):
    sut = make_sut()

    await sut.mark_posts_as_processed("key", ["mypost"])

    assert not await sut.has_posts("another_key")

import pytest

from feed_proxy.storage import MemoryPostStorage, SqlitePostStorage, create_sqlite_conn


@pytest.fixture(params=[MemoryPostStorage, SqlitePostStorage])
def make_sut(request):
    def _make_sut():
        if request.param == SqlitePostStorage:
            conn = create_sqlite_conn(":memory:")
            return SqlitePostStorage(conn)
        elif request.param == MemoryPostStorage:
            return MemoryPostStorage()
        else:
            raise ValueError("Invalid storage type")

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


async def test_any_processed_matches_when_any_id_present(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("key", ["mypost"])

    assert await sut.any_processed("key", ["other", "mypost"])


async def test_any_processed_false_when_no_id_present(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("key", ["mypost"])

    assert not await sut.any_processed("key", ["other", "another"])


async def test_any_processed_empty_post_ids_returns_false(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("key", ["mypost"])

    assert not await sut.any_processed("key", [])


async def test_any_processed_operate_only_on_passed_key(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("key", ["mypost"])

    assert not await sut.any_processed("another_key", ["mypost"])

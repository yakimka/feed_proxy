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


async def test_has_posts_true_only_after_source_marked(make_sut):
    sut = make_sut()

    assert not await sut.has_posts("source", "telegram")

    await sut.mark_posts_as_processed("source", "group", "telegram", ["mypost"])

    assert await sut.has_posts("source", "telegram")


async def test_has_posts_false_for_different_source_id(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("source", "group", "telegram", ["mypost"])

    assert not await sut.has_posts("another_source", "telegram")


async def test_has_posts_false_for_different_receiver_type(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("source", "group", "telegram", ["mypost"])

    assert not await sut.has_posts("source", "rss")


async def test_any_processed_matches_by_dedup_group_across_sources(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("a", "g", "telegram", ["mypost"])

    assert await sut.any_processed("g", "telegram", ["other", "mypost"])


async def test_any_processed_false_when_no_id_present(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("source", "group", "telegram", ["mypost"])

    assert not await sut.any_processed("group", "telegram", ["other", "another"])


async def test_any_processed_empty_post_ids_returns_false(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("source", "group", "telegram", ["mypost"])

    assert not await sut.any_processed("group", "telegram", [])


async def test_any_processed_false_for_different_dedup_group(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("source", "group", "telegram", ["mypost"])

    assert not await sut.any_processed("another_group", "telegram", ["mypost"])


async def test_any_processed_false_for_different_receiver_type(make_sut):
    sut = make_sut()
    await sut.mark_posts_as_processed("source", "group", "telegram", ["mypost"])

    assert not await sut.any_processed("group", "rss", ["mypost"])


async def test_mark_posts_as_processed_populates_both_indexes_atomically(make_sut):
    sut = make_sut()

    await sut.mark_posts_as_processed("source", "group", "telegram", ["mypost"])

    assert await sut.has_posts("source", "telegram")
    assert await sut.any_processed("group", "telegram", ["mypost"])

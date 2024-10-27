import pytest

from feed_proxy import handlers
from feed_proxy.db import schema

handler_class = handlers.FilterProcessed


@pytest.fixture()
def handler(migrated_sqlite_connection):
    return handler_class(migrated_sqlite_connection)


def test_init(migrated_sqlite_connection):
    handler = handler_class(migrated_sqlite_connection)

    assert handler.conn is migrated_sqlite_connection


def test_filter_processed_posts(
        migrated_sqlite_connection, handler, posts_parsed
):
    schema.create_processed(migrated_sqlite_connection, posts_parsed[-1])

    assert handler(posts_parsed) == posts_parsed[:9]


def test_check_processed_until_first_match(
        migrated_sqlite_connection, handler, posts_parsed
):
    schema.create_processed(migrated_sqlite_connection, posts_parsed[3])

    assert handler(posts_parsed) == posts_parsed[:3]


def test_check_all_processed_when_set_flag(
        migrated_sqlite_connection, handler, factory
):
    source = factory.source(check_processed_until_first_match=False)
    post1 = factory.post(id='post1', source=source)
    post2 = factory.post(id='post2', source=source)
    post3 = factory.post(id='post3', source=source)
    post4 = factory.post(id='post4', source=source)
    posts_parsed = [post1, post2, post3, post4]

    schema.create_processed(migrated_sqlite_connection, post2)

    assert handler(posts_parsed) == [post1, post3, post4]


def test_no_posts_for_process(
        migrated_sqlite_connection, handler, posts_parsed
):
    schema.create_processed(migrated_sqlite_connection, posts_parsed[0])

    assert handler(posts_parsed) == []

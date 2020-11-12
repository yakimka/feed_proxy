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


def test_no_posts_for_process(
        migrated_sqlite_connection, handler, posts_parsed
):
    schema.create_processed(migrated_sqlite_connection, posts_parsed[0])

    assert handler(posts_parsed) == []

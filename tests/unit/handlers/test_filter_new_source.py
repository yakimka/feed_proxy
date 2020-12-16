import pytest
from sqlalchemy import select
from sqlalchemy.sql.functions import count

from feed_proxy import handlers
from feed_proxy.conf import settings
from feed_proxy.db import schema

handler_class = handlers.FilterNewSource


@pytest.fixture()
def handler(migrated_sqlite_connection):
    return handler_class(migrated_sqlite_connection)


def test_init(migrated_sqlite_connection):
    handler = handler_class(migrated_sqlite_connection)

    assert handler.conn is migrated_sqlite_connection


def test_filter_all_posts_for_new_source(handler, posts_parsed):
    assert handler(posts_parsed) == []


def test_not_filter_posts_for_old_source(migrated_sqlite_connection, handler, posts_parsed):
    schema.create_processed(migrated_sqlite_connection, posts_parsed[1])

    assert handler(posts_parsed) == posts_parsed


def test_create_processed_entries_if_source_is_new(
        migrated_sqlite_connection, handler, posts_parsed
):
    handler(posts_parsed)

    query = select([count()]).select_from(schema.processed_table)

    assert migrated_sqlite_connection.execute(query).scalar() == settings.NUM_MESSAGES_TO_STORE

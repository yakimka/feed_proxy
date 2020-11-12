from feed_proxy.db import schema


def test_metadata():
    assert set(schema.metadata.naming_convention) == {
        'all_column_names',
        'ix',
        'uq',
        'ck',
        'fk',
        'pk',
    }


def test_is_new_source(migrated_sqlite_connection, source):
    assert schema.is_new_source(migrated_sqlite_connection, source) is True


def test_is_new_source_already_processed(migrated_sqlite_connection, source):
    query = schema.processed_table.insert().values(
        source_name=source.name,
        post_id='1234',
    )
    migrated_sqlite_connection.execute(query)

    assert schema.is_new_source(migrated_sqlite_connection, source) is False


def test_create_processed_one(migrated_sqlite_connection, posts):
    schema.create_processed(migrated_sqlite_connection, posts.regular)

    query = schema.processed_table.select()
    item = migrated_sqlite_connection.execute(query).fetchone()

    assert item.source_name == 'aiohttp releases'
    assert item.post_id == 'tag:github.com,2008:Repository/13258039/v3.7.3'
    assert item.created


def test_create_processed_many(migrated_sqlite_connection, posts_parsed):
    schema.create_processed(migrated_sqlite_connection, posts_parsed)

    query = schema.processed_table.select()
    res = migrated_sqlite_connection.execute(query).fetchall()
    items = [(item.source_name, item.post_id) for item in res]

    assert items == [
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.7.3'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.7.2'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.7.1'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.7.0'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.7.0b1'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.7.0b0'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.6.3'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v4.0.0a1'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.6.2'),
        ('aiohttp releases', 'tag:github.com,2008:Repository/13258039/v3.6.2a2')]


def test_is_post_processed(migrated_sqlite_connection, posts):
    schema.create_processed(migrated_sqlite_connection, posts.regular)

    assert schema.is_post_processed(migrated_sqlite_connection, posts.regular) is True


def test_is_post_not_processed(migrated_sqlite_connection, posts):
    schema.create_processed(migrated_sqlite_connection, posts[0])

    assert schema.is_post_processed(migrated_sqlite_connection, posts[1]) is False

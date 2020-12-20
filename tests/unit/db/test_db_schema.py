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

    assert item.source_name == 'feed_proxy releases'
    assert item.post_id == 'regular'
    assert item.created


def test_create_processed_many(migrated_sqlite_connection, posts_parsed):
    schema.create_processed(migrated_sqlite_connection, posts_parsed)

    query = schema.processed_table.select()
    res = migrated_sqlite_connection.execute(query).fetchall()
    items = [(item.source_name, item.post_id) for item in res]

    assert items == [
        ('feed_proxy releases', 'regular'),
        ('feed_proxy releases', 'has_published'),
        ('feed_proxy releases', 'wo_date'),
        ('feed_proxy releases', 'wo_author'),
        ('feed_proxy releases', 'has_tags'),
        ('feed_proxy releases', 'audio_gt_20mb'),
        ('feed_proxy releases', 'audio_lt_20mb'),
        ('feed_proxy releases', 'audio_0b'),
        ('feed_proxy releases', 'empty_author'),
        ('feed_proxy releases', 'https://github.com/yakimka/feed_proxy/releases/tag/91')]


def test_is_post_processed(migrated_sqlite_connection, posts):
    schema.create_processed(migrated_sqlite_connection, posts.regular)

    assert schema.is_post_processed(migrated_sqlite_connection, posts.regular) is True


def test_is_post_not_processed(migrated_sqlite_connection, posts):
    schema.create_processed(migrated_sqlite_connection, posts[0])

    assert schema.is_post_processed(migrated_sqlite_connection, posts[1]) is False

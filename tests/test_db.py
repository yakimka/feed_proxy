import pytest

from feed_proxy import db


@pytest.fixture
def processed():
    """
    Create processed entry in db with parameters:
    source_name = 'habr'
    post_id = 1
    receiver_id = 'telegram_chat'
    """

    return db.create_processed_entry('habr', 1, 'telegram_chat')


@pytest.fixture
def mock_create_tables(mocker):
    """Mock feed_proxy.db.database.create_tables
    """

    return mocker.patch('feed_proxy.db.database.create_tables')


@pytest.fixture
def mock_get_tables_empty(mocker):
    """Patch feed_proxy.db.database.get_tables with '[]' (empty list) return value
    """

    return mocker.patch('feed_proxy.db.database.get_tables', return_value=[])


@pytest.fixture
def mock_get_tables_with_values(mocker):
    """Patch feed_proxy.db.database.get_tables with '[1]' return value
    """

    return mocker.patch('feed_proxy.db.database.get_tables', return_value=[1])


@pytest.mark.emptydb
def test_init(mock_create_tables, mock_get_tables_empty):
    db.init()
    db.database.create_tables.assert_called_once()


@pytest.mark.emptydb
def test_init_dont_create_tables_if_already_exists(mock_create_tables, mock_get_tables_with_values):
    db.init()
    db.database.create_tables.assert_not_called()


@pytest.mark.parametrize('source_name,expected', [
    ('dummy', True),
    ('habr', False),
])
def test_is_source_new(processed, source_name, expected):
    assert db.is_source_new(source_name) is expected


@pytest.mark.parametrize('source_name,receiver_id,expected', [
    ('dummy', 'new_telegram_chat', True),
    ('dummy', 'telegram_chat', True),
    ('habr', 'new_telegram_chat', True),
    ('habr', 'telegram_chat', False),
])
def test_is_source_new_for_receiver(processed, source_name, receiver_id, expected):
    assert db.is_source_new_for_receiver(source_name, receiver_id) is expected


@pytest.mark.parametrize('source_name,post_id,receiver_id,expected', [
    ('dummy', 1, 'new_telegram_chat', False),
    ('dummy', 1, 'telegram_chat', False),
    ('habr', 1, 'new_telegram_chat', False),
    ('habr', 1, 'telegram_chat', True),
])
def test_is_post_processed_for_receiver(processed, source_name, post_id, receiver_id, expected):
    assert db.is_post_processed_for_receiver(source_name, post_id, receiver_id) is expected


def test_create_processed_entry():
    db.create_processed_entry('habr', 1, 'telegram_chat')

    assert db.is_post_processed_for_receiver('habr', 1, 'telegram_chat')

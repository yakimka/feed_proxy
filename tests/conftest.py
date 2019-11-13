import pytest
import requests
from peewee import SqliteDatabase
from requests_mock import ANY

from feed_proxy.config import ConfigParser, ConfigStorage
from feed_proxy.db import MODELS
from feed_proxy.parsers import Post, Attachment
from feed_proxy.senders import TelegramSender
from feed_proxy.utils import AttrDict

test_db = SqliteDatabase(':memory:')


@pytest.fixture(autouse=True)
# http://docs.peewee-orm.com/en/latest/peewee/database.html#testing-peewee-applications
def setup_db(request):
    """Create test db on each test and destroy it after test is finished
    """

    # Bind model classes to test db. Since we have a complete list of
    # all models, we do not need to recursively bind dependencies.
    test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)

    test_db.connect()
    if not 'emptydb' in request.keywords:
        test_db.create_tables(MODELS)

    yield

    # Not strictly necessary since SQLite in-memory databases only live
    # for the duration of the connection, and in the next step we close
    # the connection...but a good practice all the same.
    test_db.drop_tables(MODELS)

    # Close connection to db.
    test_db.close()

    # If we wanted, we could re-bind the models to their original
    # database here. But for tests this is probably not necessary.


@pytest.fixture
def dict_source_settings():
    """Example source setting represented in dict
    """

    return {'url': 'https://example.com/feed.xml',
            'parser_class': 'RSSFeedParser',
            'sender_class': 'TelegramSender',
            'tags': '',
            'add_parsed_tags': 'no',
            'disable_link_preview': 'yes',
            'receivers': '-1001234567890 -1001234567891 -1001234567892'}


@pytest.fixture
def dict_config(dict_source_settings):
    """Example feed_proxy config represented in dict
    """

    return {
        'DEFAULT': {'layout_template': '{message}<br><br>{source_tags}',
                    'post_template': '<a href="{url}">{title}</a>'},
        'telegram': {'token': 'token'},
        'example source': dict_source_settings
    }


@pytest.fixture
def config(dict_config):
    """Parsed config from "dict_config" fixture
    """

    return ConfigParser().get_from_dict(dict_config)


@pytest.fixture
def config_storage(config):
    """ConfigStorage instance created from "config" fixture
    """

    return ConfigStorage(config)


@pytest.fixture
def mock_config_parser(config, mocker):
    """
    Patch "get_or_create_and_exit" method of "ConfigParser" class.
    Return value replaced with "config" fixture
    """

    return mocker.patch('feed_proxy.config.ConfigParser.get_or_create_and_exit',
                        return_value=config)


@pytest.fixture
def mp3_enclosure():
    """AttrDict enclosure with audio/mp3 type
    """

    return AttrDict({'url': 'https://example.com/example.mp3', 'type': 'audio/mp3'})


@pytest.fixture
def aac_enclosure():
    """AttrDict enclosure with audio/aac type
    """

    return AttrDict({'url': 'https://example.com/example.aac', 'type': 'audio/aac'})


@pytest.fixture
def jpeg_enclosure():
    """AttrDict enclosure with image/jpeg type
    """

    return AttrDict({'url': 'https://example.com/example.jpeg', 'type': 'image/jpeg'})


@pytest.fixture
def mp4_enclosure():
    """AttrDict enclosure with video/mp4 type
    """

    return AttrDict({'url': 'https://example.com/example.mp4', 'type': 'video/mp4'})


@pytest.fixture
def mp3_attachment(post, mp3_enclosure):
    """Attachment instance created from "mp3_enclosure"
    """

    return Attachment(mp3_enclosure, post=post)


@pytest.fixture
def raw_post(mp3_enclosure):
    """AttrDict structure represented raw post with mp3 enclosure parsed from feed
    """

    return AttrDict({
        'author': 'Author',
        'enclosures': [mp3_enclosure],
        'id': '123',
        'link': 'https://example.com/post',
        'published': '2019-10-10',
        'summary': 'Some summary',
        'tags': [{'term': 'Python'}, {'term': 'Django'}],
        'title': 'Some title',
    })


@pytest.fixture
def post(raw_post):
    """Post instance created from "raw_post" fixture
    """

    return Post(raw_post)


@pytest.fixture
def post_factory(raw_post):
    """
    Post factory. By default post will be created with "raw_post" fixture data.
    But you can replace this data by passing your data with "mapping" arg.
    """

    def factory(mapping=None):
        if mapping is None:
            mapping = {}
        return Post({**raw_post, **mapping})

    return factory


@pytest.fixture
def mock_download_file_url(requests_mock):
    """Mock file url (get) with "file content" content
    """

    return requests_mock.get(ANY, content=b'file content')


@pytest.fixture
def mock_get_file_info_51mb(requests_mock, mp3_attachment):
    """
    Mock file url (head) with "content-length" 51MB
    and "content-type" headers "audio/mp3"
    """

    return requests_mock.head(ANY, headers={
        'content-length': str(51 * 1024 * 1024),
        'content-type': mp3_attachment.type
    })


@pytest.fixture
def mock_get_file_info_21mb(requests_mock, mp3_attachment):
    """
    Mock file url (head) with "content-length" 21MB
    and "content-type" headers "audio/mp3"
    """

    return requests_mock.head(ANY, headers={
        'content-length': str(21 * 1024 * 1024),
        'content-type': mp3_attachment.type
    })


@pytest.fixture
def mock_get_file_info_1mb(requests_mock, mp3_attachment):
    """
    Mock file url (head) with "content-length" 1MB
    and "content-type" headers "audio/mp3"
    """

    return requests_mock.head(ANY, headers={
        'content-length': str(1 * 1024 * 1024),
        'content-type': mp3_attachment.type
    })


@pytest.fixture
def mock_connection_error(requests_mock):
    """Mock any verb with any url raises "requests.exceptions.ConnectionError"
    """

    return requests_mock.register_uri(ANY, ANY, exc=requests.exceptions.ConnectionError)


@pytest.fixture
def mocked_tg_sender_class(mocker, mock_config_parser):
    """Mock "telebot.TeleBot" and set it
    to "TelegramSender.mocked_bot" attribute.

    Return TelegramSender class
    """

    mock = mocker.patch('telebot.TeleBot')
    TelegramSender.mocked_bot = mock

    return TelegramSender

@pytest.fixture
def tg_sender(request, mocked_tg_sender_class):
    """Return "TelegramSender" instance.
    "chat_id" and "message" params are taken
    from the module variables "CHAT_ID" and "MESSAGE"
    """

    chat_id = getattr(request.module, 'CHAT_ID')
    message = getattr(request.module, 'MESSAGE')
    return mocked_tg_sender_class(chat_id, message)

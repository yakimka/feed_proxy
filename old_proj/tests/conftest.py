import os
from collections import namedtuple
from datetime import datetime
from types import SimpleNamespace

import pytest
from alembic.command import upgrade
from requests_mock import ANY
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, drop_database

from feed_proxy.conf import settings
from feed_proxy.schema import Attachment, Author, Post
from feed_proxy.test.factory import Factory
from feed_proxy.utils import make_alembic_config

TESTS_PATH = os.path.dirname(__file__)


@pytest.fixture()
def sqlite():
    tmp_url = 'sqlite:////tmp/test_feed_proxy.sqlite3'
    create_database(tmp_url)

    try:
        yield tmp_url
    finally:
        drop_database(tmp_url)


@pytest.fixture()
def alembic_config(sqlite):
    cmd_options = SimpleNamespace(config='alembic.ini', name='alembic',
                                  db_url=sqlite, raiseerr=False, x=None, is_test=True)
    return make_alembic_config(cmd_options)


@pytest.fixture()
def migrated_sqlite(alembic_config, sqlite):
    upgrade(alembic_config, 'head')
    return sqlite


@pytest.fixture()
def migrated_sqlite_connection(migrated_sqlite):
    engine = create_engine(migrated_sqlite)
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()
        engine.dispose()


@pytest.fixture(autouse=True, scope='session')
def _setup_settings():
    settings.configure(
        sources_path=os.path.join(TESTS_PATH, 'sources.ini'),
        PROXY_BOT_URL='http://localhost:8081',
    )


@pytest.fixture(scope='session')
def feed_xml_factory():
    def factory(*enties: str, base: str = 'feed_base'):
        feed_items = []
        for item in enties:
            with open(os.path.join(TESTS_PATH, 'fixtures', f'{item}.xml'), 'r') as fp:
                feed_items.append(fp.read())

        with open(os.path.join(TESTS_PATH, 'fixtures', f'{base}.xml'), 'r') as fp:
            feed_base = fp.read()

        return feed_base.format(entries=''.join(feed_items))

    return factory


@pytest.fixture(scope='session')
def feed_xml(feed_xml_factory):
    return feed_xml_factory(
        'regular',
        'has_published',
        'wo_date',
        'wo_author',
        'has_tags',
        'audio_gt_20mb',
        'audio_lt_20mb',
        'audio_0b',
        'empty_author',
        'wo_id',
    )


@pytest.fixture(scope='session')
def httpserver_listen_address():
    return 'localhost', 45432


@pytest.fixture()
def example_feed_server(httpserver, feed_xml):
    httpserver.expect_request('/feed.xml').respond_with_data(feed_xml, content_type='text/plain')
    httpserver.expect_request('/500').respond_with_data('Server error', status=500)
    return httpserver


@pytest.fixture()
def posts(source):
    posts_ = namedtuple('posts', [
        'regular',
        'has_published',
        'wo_date',
        'wo_author',
        'has_tags',
        'audio_gt_20mb',
        'audio_lt_20mb',
        'audio_0b',
        'empty_author',  # authors -> [{}]
        'wo_id',
    ])

    return posts_(
        Post(id='regular', author='yakimka', authors=(Author(name='yakimka', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/100',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 100 release',
             source=source, tags=(), attachments=(),
             published=datetime(2020, 11, 18, 19, 38, 17)),
        Post(id='has_published', author='yakimka',
             authors=(Author(name='yakimka', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/99',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 99 release',
             source=source, tags=(), attachments=(),
             published=datetime(2020, 10, 27, 8, 9, 32)),
        Post(id='wo_date', author='yakimka', authors=(Author(name='yakimka', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/98',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 98 release',
             source=source, tags=(), attachments=(), published=None),
        Post(id='wo_author', author='feed_proxy releases',
             authors=(Author(name='feed_proxy releases', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/97',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 97 release',
             source=source, tags=(), attachments=(),
             published=datetime(2020, 10, 24, 8, 39, 14)),
        Post(id='has_tags', author='yakimka', authors=(Author(name='yakimka', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/96',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 96 release',
             source=source, tags=('Python', 'агрегатор rss', 'feed proxy'),
             attachments=(), published=datetime(2020, 10, 22, 14, 15, 1)),
        Post(id='audio_gt_20mb', author='yakimka',
             authors=(Author(name='yakimka', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/95',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 95 release',
             source=source, tags=(), attachments=(
                Attachment(href='http://localhost:45432/song.mp3', type='audio/mpeg',
                           length=21652106),), published=datetime(2020, 10, 21, 18, 54, 4)),
        Post(id='audio_lt_20mb', author='yakimka',
             authors=(Author(name='yakimka', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/94',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 94 release',
             source=source, tags=(), attachments=(
                Attachment(href='http://localhost:45432/song.mp3', type='audio/mpeg',
                           length=19999999),), published=datetime(2020, 10, 12, 10, 36, 15)),
        Post(id='audio_0b', author='yakimka', authors=(Author(name='yakimka', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/93',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 93 release',
             source=source, tags=(), attachments=(
                Attachment(href='http://localhost:45432/song.mp3', type='audio/mpeg', length=0),),
             published=datetime(2019, 10, 9, 11, 30, 4)),
        Post(id='empty_author', author='feed_proxy releases',
             authors=(Author(name='feed_proxy releases', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/92',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 92 release',
             source=source, tags=(), attachments=(),
             published=datetime(2019, 10, 9, 17, 5, 13)),
        Post(id='https://github.com/yakimka/feed_proxy/releases/tag/91',
             author='yakimka', authors=(Author(name='yakimka', href='', email=''),),
             url='https://github.com/yakimka/feed_proxy/releases/tag/91',
             summary='Lorem ipsum dolor sit amet, consectetur adipisicing.>',
             title='feed_proxy 91 release',
             source=source, tags=(), attachments=(),
             published=datetime(2019, 10, 9, 17, 4, 7)),
    )


@pytest.fixture()
def posts_parsed(posts):
    return list(posts[:10])


@pytest.fixture()
def mock_download_file(requests_mock):
    """Mock file url (get) with "file content" content
    """

    return requests_mock.get(ANY, content=b'file content')


@pytest.fixture()
def factory():
    return Factory


@pytest.fixture()
def source(factory):
    return factory.source()

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
from feed_proxy.schema import Attachment, Author, Post, Source
from feed_proxy.utils import make_alembic_config


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
async def migrated_sqlite(alembic_config, sqlite):
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
        sources_path=os.path.join(settings.BASE_DIR, 'tests', 'sources.ini'),
        PROXY_BOT_URL='http://localhost:8081',
    )


@pytest.fixture(scope='session')
def feed_xml():
    base_path = os.path.dirname(__file__)
    with open(os.path.join(base_path, 'fixtures', 'feed.xml'), 'r') as fp:
        return fp.read()


@pytest.fixture()
def httpserver_listen_address():
    return 'localhost', 45432


@pytest.fixture()
def example_feed_server(httpserver, feed_xml):
    httpserver.expect_request('/feed.xml').respond_with_data(feed_xml, content_type='text/plain')
    httpserver.expect_request('/500').respond_with_data('Server error', status=500)
    return httpserver


@pytest.fixture()
def source():
    return Source(
        name='aiohttp releases',
        url='http://localhost:45432/feed.xml',
        receiver='-1001234567890',
        post_template='<a href="{url}">{title}</a>\n\n{source_tags} {post_tags}',
        encoding='utf-8',
        disable_link_preview=True,
        tags=('hash', 'tag')
    )


@pytest.fixture()
def error_source():
    return Source(
        name='server error feed',
        url='http://localhost:45432/500',
        receiver='-1001234567890',
        post_template='<a href="{url}">{title}</a>\n\n{source_tags} {post_tags}',
        encoding='utf-8',
        disable_link_preview=True,
        tags=tuple()
    )


@pytest.fixture()
def posts(source):
    posts_ = namedtuple('posts', [
        'regular',
        'has_published',
        'wo_date',
        'has_updated',
        'has_tags',
        'audio_gt_20mb',
        'audio_lt_20mb',
        'audio_0b',
        'original2',
        'original3',
    ])
    return posts_(
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v3.7.3',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.7.3',
             summary='Use Brotli instead of brotlipy<br />',
             title='aiohttp 3.7.3 release', tags=tuple(), attachments=tuple(),
             published=datetime(2020, 11, 18, 19, 38, 17)),
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v3.7.2',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.7.2',
             summary='<h2>Bugfixes</h2>',
             title='aiohttp 3.7.2 release', tags=tuple(), attachments=tuple(),
             published=datetime(2020, 10, 27, 8, 9, 32)),
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v3.7.1',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.7.1',
             summary="<h2>Bugfixes</h2>",
             title='aiohttp 3.7.1 release', tags=tuple(), attachments=tuple(), published=None),
        Post(author='aiohttp releases', source=source, authors=(Author(name='aiohttp releases'),),
             id='tag:github.com,2008:Repository/13258039/v3.7.0',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.7.0',
             summary='aiohttp 3.7.0 release',
             title='aiohttp 3.7.0 release', tags=tuple(), attachments=tuple(),
             published=datetime(2020, 10, 24, 9, 39, 14)),
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v3.7.0b1',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.7.0b1',
             summary='<p>Release 3.7.0b1</p>', title='v3.7.0b1',
             tags=('Python', 'асинхронное программирование', 'aiohttp'), attachments=tuple(),
             published=datetime(2020, 10, 22, 15, 15, 1)),
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v3.7.0b0',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.7.0b0',
             summary='<p>Release 3.7.0b0</p>', title='v3.7.0b0', tags=tuple(),
             attachments=(Attachment(href='http://localhost:45432/song.mp3', type='audio/mpeg',
                                     length=21652106),),
             published=datetime(2020, 10, 21, 19, 54, 4)),
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v3.6.3',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.6.3',
             summary='<p>Release 3.6.3</p>', title='v3.6.3', tags=tuple(),
             attachments=(Attachment(href='http://localhost:45432/song.mp3', type='audio/mpeg',
                                     length=19999999),),
             published=datetime(2020, 10, 12, 11, 36, 15)),
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v4.0.0a1',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v4.0.0a1',
             summary='No content.', title='v4.0.0a1', tags=tuple(),
             attachments=(Attachment(href='http://localhost:45432/song.mp3', type='audio/mpeg',
                                     length=0),),
             published=datetime(2019, 10, 9, 12, 30, 4)),
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v3.6.2',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.6.2',
             summary="<p>It contains several bufixes.</p>",
             title='aiohttp 3.6.2 release', tags=tuple(), attachments=tuple(),
             published=datetime(2019, 10, 9, 18, 5, 13)),
        Post(author='asvetlov', authors=(Author(name='asvetlov'),), source=source,
             id='tag:github.com,2008:Repository/13258039/v3.6.2a2',
             url='https://github.com/aio-libs/aiohttp/releases/tag/v3.6.2a2',
             summary='No content.', title='v3.6.2a2', tags=tuple(), attachments=tuple(),
             published=datetime(2019, 10, 9, 18, 4, 7))
    )


@pytest.fixture()
def posts_parsed(posts):
    return list(posts)


@pytest.fixture()
def mock_download_file(requests_mock):
    """Mock file url (get) with "file content" content
    """

    return requests_mock.get(ANY, content=b'file content')

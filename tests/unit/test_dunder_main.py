from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from feed_proxy import __main__ as dunder_main


@pytest.fixture()
def mock_fetch_sources(mocker: MockerFixture, factory, feed_xml):
    m_fetch_sources = mocker.patch.object(dunder_main, 'fetch_sources')
    error_source = factory.source(
        name='server error feed',
        url='http://localhost:45432/500',
    )
    m_fetch_sources.return_value = [
        (factory.source(), 200, feed_xml),
        (error_source, 500, 'Server error')
    ]

    return m_fetch_sources


def test_main(
        mock_fetch_sources,
        mocker: MockerFixture,
        feed_xml,
        migrated_sqlite_connection
):
    m_parse_posts = mocker.patch.object(dunder_main, 'parse_posts')
    mocked_handlers = [Mock(), Mock()]
    mocker.patch.object(dunder_main, 'HANDLERS', mocked_handlers)
    m_settings = mocker.patch.object(dunder_main, 'settings')
    m_create_engine = mocker.patch.object(dunder_main, 'create_engine')
    m_parse_args = mocker.patch.object(dunder_main.parser, 'parse_args')
    m_args = m_parse_args.return_value

    dunder_main.main()

    mock_fetch_sources.assert_called_once_with()
    m_parse_posts.assert_called_once_with(mock_fetch_sources.return_value)

    for handler in mocked_handlers:
        handler.assert_called_once_with(m_create_engine().connect().__enter__())

    mocked_handlers[0].return_value.assert_called_once_with(m_parse_posts.return_value)
    mocked_handlers[1].return_value.assert_called_once_with(mocked_handlers[0]().return_value)
    m_settings.configure.assert_called_once_with(
        m_args.sources_file,
        PROXY_BOT_URL=m_args.proxy_bot_url
    )

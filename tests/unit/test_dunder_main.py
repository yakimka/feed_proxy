from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from feed_proxy import __main__ as dunder_main


@pytest.fixture()
def mock_fetch_sources(mocker: MockerFixture, source, feed_xml, error_source):
    m_fetch_sources = mocker.patch.object(dunder_main, 'fetch_sources')
    m_fetch_sources.return_value = [
        (source, 200, feed_xml),
        (error_source, 500, 'Server error')
    ]

    return m_fetch_sources


@pytest.mark.asyncio
async def test_run(
        mock_fetch_sources, mocker: MockerFixture, source, feed_xml, migrated_sqlite_connection
):
    m_parse_posts = mocker.patch.object(dunder_main, 'parse_posts')
    mocked_handlers = [Mock(), Mock()]
    mocker.patch.object(dunder_main, 'HANDLERS', mocked_handlers)

    await dunder_main.run(migrated_sqlite_connection)

    mock_fetch_sources.assert_called_once_with()
    m_parse_posts.assert_called_once_with(mock_fetch_sources.return_value)

    for handler in mocked_handlers:
        handler.assert_called_once_with(migrated_sqlite_connection)

    mocked_handlers[0].return_value.assert_called_once_with(m_parse_posts.return_value)
    mocked_handlers[1].return_value.assert_called_once_with(mocked_handlers[0]().return_value)

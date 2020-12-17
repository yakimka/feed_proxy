from unittest.mock import patch

import pytest
from requests import RequestException

from feed_proxy import fetchers

pytestmark = [pytest.mark.usefixtures('example_feed_server')]


def test_fetch_text_for_source(source):
    res_source, status, text = fetchers.fetch_text_for_source(source)

    assert 200 == status
    assert 'aiohttp 3.7.2 release' in text
    assert source == res_source


@patch.object(fetchers.requests, 'get', side_effect=RequestException)
def test_fetch_text_for_source_on_request_error(m_get, source):
    res_source, status, text = fetchers.fetch_text_for_source(source)

    assert status is None
    assert text == ''
    assert source == res_source


@patch.object(fetchers.requests, 'get', side_effect=RequestException)
def test_fetch_text_for_source_log_error_on_request_error(m_get, source, caplog):
    fetchers.fetch_text_for_source(source)

    assert caplog.records[0].levelname == 'ERROR'
    assert "Can't fetch 'http://localhost:45432/feed.xml' from 'aiohttp releases'" in caplog.text


def test_fetch_text():
    res = fetchers.fetch_sources()
    source, status, text = res[0]

    assert 200 == status
    assert 'aiohttp 3.7.2 release' in text
    assert 'aiohttp releases' == source.name


def test_fetch_error():
    res = fetchers.fetch_sources()
    source, status, text = res[1]

    assert 500 == status
    assert 'Server error' == text
    assert 'server error feed' == source.name

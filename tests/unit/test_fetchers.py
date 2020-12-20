from unittest.mock import patch

import pytest
from requests import RequestException

from feed_proxy import fetchers
from feed_proxy.schema import Source

pytestmark = [pytest.mark.usefixtures('example_feed_server')]


def test_fetch_text_for_source(source):
    res_source, status, text = fetchers.fetch_text_for_source(source)

    assert 200 == status
    assert 'feed_proxy 100 release' in text
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
    assert "Can't fetch 'http://localhost:45432/feed.xml' from 'feed_proxy releases'" in caplog.text


@patch.object(fetchers.requests, 'get')
def test_fetch_text_for_source_specify_encoding(m_get, source_data, caplog):
    source_data['encoding'] = 'UtF-8'
    fetchers.fetch_text_for_source(Source(**source_data))

    assert m_get.return_value.encoding == 'UtF-8'


def test_fetch_text():
    res = fetchers.fetch_sources()
    source, status, text = res[0]

    assert 200 == status
    assert 'feed_proxy 100 release' in text
    assert 'feed_proxy releases' == source.name


def test_fetch_error():
    res = fetchers.fetch_sources()
    source, status, text = res[1]

    assert 500 == status
    assert 'Server error' == text
    assert 'server error feed' == source.name

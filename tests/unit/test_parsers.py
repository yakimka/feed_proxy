from unittest.mock import patch

import pytest

from feed_proxy import parsers
from feed_proxy.schema import Source


def test_rss_feed_posts_parser(feed_xml, source, posts_parsed, caplog):
    posts = parsers.rss_feed_posts_parser(source, feed_xml)

    assert posts_parsed == posts
    assert caplog.records[0].levelname == 'WARNING'
    assert "Can't parse published date: 'aiohttp releases'; 'aiohttp 3.7.1 release'" in caplog.text


def test_rss_feed_posts_parser_when_empty_text(source):
    posts = parsers.rss_feed_posts_parser(source, '')

    assert [] == posts


def test_rss_feed_posts_parser_source_with_custom_url_field(source_data, feed_xml):
    source_data['url_field'] = 'custom_field'
    posts = parsers.rss_feed_posts_parser(Source(**source_data), feed_xml)

    assert posts[0].url == 'some value'


@patch.object(parsers.feedparser, 'parse', return_value={'entries': [{}]})
def test_rss_feed_posts_parser_unexpected_error(m_parse, source, feed_xml):
    with pytest.raises(ValueError) as e:  # noqa PT011
        parsers.rss_feed_posts_parser(source, feed_xml)

    assert "Can't process entry. Source: 'aiohttp releases'" in str(e)
    assert 'Entry: {}' in str(e)


class TestParsePostsFunc:
    @pytest.fixture(autouse=True)
    def _setup_method(self, source, feed_xml, error_source, posts_parsed):
        self.error_source = error_source

        self.s200 = (source, 200, feed_xml)
        self.posts = posts_parsed
        self.s400 = (error_source, 400, 'Client error')
        self.s500 = (error_source, 500, 'Server error')
        self.empty_text = (source, 200, '')
        self.err = (error_source, None, '')

    def test_parse_posts(self):
        results = parsers.parse_posts([self.s200])

        assert results == self.posts

    def test_parse_posts_from_empty_text(self):
        results = parsers.parse_posts([self.empty_text])

        assert results == []

    def test_parse_posts_on_request_error(self):
        results = parsers.parse_posts([self.err])

        assert results == []

    def test_parse_posts_many(self):
        results = parsers.parse_posts([self.s200, self.s400, self.empty_text, self.s500, self.s200])

        assert results == self.posts + self.posts

    def test_warning_when_cant_find_posts(self, caplog):
        parsers.parse_posts([self.empty_text])

        assert caplog.records[0].levelname == 'WARNING'
        assert ("Can't find posts in 'http://localhost:45432/feed.xml'"
                " from 'aiohttp releases'. Text:\n") in caplog.text

    def test_warning_when_error_status(self, caplog):
        parsers.parse_posts([self.s400])

        assert caplog.records[0].levelname == 'WARNING'
        assert "Status code 400 when trying to fetch 'server error feed'. Text:\nClient error"

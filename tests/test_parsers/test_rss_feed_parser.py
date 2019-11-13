import pytest

from feed_proxy.config import SourceSettings, ConfigParser
from feed_proxy.parsers import RSSFeedParser, Post


@pytest.fixture
def mock_feedparser_parse(mocker, raw_post):
    """Patch "feedparser.parse" method return value with MockFeed dummy class
    """

    class MockFeed:
        entries = [raw_post, raw_post, raw_post]

    return mocker.patch('feedparser.parse', return_value=MockFeed())


@pytest.fixture
def source_settings(config):
    """SourceSettings instance with 'example source' and 'config['example source']'
    from "config" fixture
    """

    return SourceSettings('example source', config['example source'])


@pytest.fixture
def rss_feed_parser(source_settings):
    """RSSFeedParser instance created from "source_settings" fixture
    """

    return RSSFeedParser(source_settings)


def test_parse(rss_feed_parser, mock_feedparser_parse):
    rss_feed_parser.parse()

    assert len(rss_feed_parser.posts) == 3
    assert all([type(post) is Post for post in rss_feed_parser.posts])

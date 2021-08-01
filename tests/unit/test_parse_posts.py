from unittest.mock import call

import pytest
from pytest_mock import MockerFixture

from feed_proxy import parsers

parse_posts_func = parsers.parse_posts

pytestmark = [pytest.mark.usefixtures('mock_rss_feed_posts_parser')]


@pytest.fixture()
def mock_rss_feed_posts_parser(mocker: MockerFixture, posts):
    mock = mocker.patch.object(parsers, 'rss_feed_posts_parser')
    mock.return_value = [posts.regular]
    return mock


def test_parse_posts(source, posts, mock_rss_feed_posts_parser):
    fetched1 = (source, 200, 'regular post1 xml')
    fetched2 = (source, 200, 'regular post2 xml')
    results = parse_posts_func([fetched1, fetched2])

    mock_rss_feed_posts_parser.assert_has_calls([
        call(source, 'regular post1 xml'),
        call(source, 'regular post2 xml'),
    ])
    assert results == [posts.regular, posts.regular]


@pytest.mark.parametrize('status_code', [None, 400, 500])
def test_on_request_error(source, posts, mock_rss_feed_posts_parser, status_code):
    fetched1 = (source, status_code, 'Error')
    fetched2 = (source, 200, 'regular post2 xml')
    results = parse_posts_func([fetched1, fetched2])

    mock_rss_feed_posts_parser.assert_called_once_with(source, 'regular post2 xml')
    assert results == [posts.regular]


@pytest.mark.parametrize('status_code', [None, 400])
def test_logger_message_on_request_error(source, posts, caplog, status_code):
    fetched = (source, status_code, 'Some Error')
    parse_posts_func([fetched])

    assert caplog.records[0].levelname == 'WARNING'
    assert (f"Status code {status_code} when trying to fetch 'http://localhost:45432/feed.xml'"
            " from 'feed_proxy releases'. Text:\nSome Error"
            in caplog.text)


def test_cant_find_posts(source, mock_rss_feed_posts_parser, caplog):
    fetched = (source, 200, '')
    mock_rss_feed_posts_parser.return_value = []
    results = parsers.parse_posts([fetched])

    assert results == []


def test_logger_message_when_cant_find_posts(source, mock_rss_feed_posts_parser, caplog):
    fetched = (source, 200, '')
    mock_rss_feed_posts_parser.return_value = []
    parsers.parse_posts([fetched])

    assert caplog.records[0].levelname == 'WARNING'
    assert ("Can't find posts in 'http://localhost:45432/feed.xml'"
            " from 'feed_proxy releases'. Text:\n") in caplog.text


def test_filter_posts_on_exclude_post_by_tags(factory, posts, mock_rss_feed_posts_parser):
    source = factory.source(exclude_post_by_tags=('python',))
    fetched = (source, 200, 'some posts in xml')
    mock_rss_feed_posts_parser.return_value = [posts.regular, posts.has_tags]
    results = parse_posts_func([fetched])

    assert results == [posts.regular]


def test_dont_filter_posts_by_custom_source_tags(
        factory,
        posts,
        mock_rss_feed_posts_parser
):
    source = factory.source(tags=('custom_tag',), exclude_post_by_tags=('custom_tag',))
    fetched = (source, 200, 'some posts in xml')
    mock_rss_feed_posts_parser.return_value = [posts.regular, posts.has_tags]
    results = parse_posts_func([fetched])

    assert results == [posts.regular, posts.has_tags]

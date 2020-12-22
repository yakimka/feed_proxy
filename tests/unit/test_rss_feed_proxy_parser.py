import pytest

from feed_proxy import parsers

parser_func = parsers.rss_feed_posts_parser


@pytest.mark.parametrize('post_type', [
    'regular',
    'has_published',
    'wo_date',
    'wo_author',
    'has_tags',
    'audio_gt_20mb',
    'audio_lt_20mb',
    'audio_0b',
    'empty_author',  # authors parsed like [{}]
    'wo_id',  # hacker news has no id tag
    'wrong_date',
])
def test_parse_posts(source, posts, post_type, feed_xml_factory):
    feed_xml = feed_xml_factory(post_type)
    parsed_posts = parser_func(source, feed_xml)

    assert parsed_posts[0] == getattr(posts, post_type)


def test_parse_feed_wo_entries(source, feed_xml_factory):
    parsed_posts = parser_func(source, feed_xml_factory())

    assert parsed_posts == []


def test_parse_empty_text(source):
    parsed_posts = parser_func(source, '')

    assert parsed_posts == []


def test_logger_message_when_cant_parse_published_date(source, feed_xml_factory, caplog):
    parser_func(source, feed_xml_factory('wo_date'))

    assert caplog.records[0].levelname == 'WARNING'
    assert ("Can't parse published date: 'feed_proxy releases'; 'feed_proxy 98 release'"
            in caplog.text)


def test_logger_message_when_parse_wrong_published_date(source, feed_xml_factory, caplog):
    parser_func(source, feed_xml_factory('wrong_date'))

    assert caplog.records[0].levelname == 'WARNING'
    assert ("Can't parse 'time.struct_time(tm_year=1, tm_mon=1, tm_mday=1, tm_hour=0, tm_min=0,"
            " tm_sec=0, tm_wday=0, tm_yday=1, tm_isdst=0)' to datetime."
            " Source: feed_proxy releases") in caplog.text


def test_rss_feed_posts_parser_source_with_custom_url_field(factory, feed_xml_factory):
    source = factory.source(url_field='custom_field')
    parsed_posts = parser_func(source, feed_xml_factory('regular'))

    assert parsed_posts[0].url == 'some value'


def test_rss_feed_posts_parser_source_with_custom_id_field(factory, feed_xml_factory):
    source = factory.source(id_field='link')
    parsed_posts = parser_func(source, feed_xml_factory('regular'))

    assert parsed_posts[0].id == 'https://github.com/yakimka/feed_proxy/releases/tag/100'


def test_rss_feed_posts_parser_unexpected_error(source, feed_xml_factory):
    with pytest.raises(ValueError, match="Can't process entry. Source: 'feed_proxy releases'"):
        parser_func(source, feed_xml_factory('wo_link'))

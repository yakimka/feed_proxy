from feed_proxy import handlers


def test_make_source_mapping(source, posts_parsed):
    result = handlers.make_source_mapping(posts_parsed[:2])

    assert result == {source: posts_parsed[:2]}


def test_make_source_empty_posts():
    result = handlers.make_source_mapping([])

    assert result == {}

from unittest.mock import patch

from feed_proxy import schema


@patch.object(schema, 'make_hash_tags', return_value=['#hash', '#tag'])
def test_hash_tags(m_make_hash_tags, source):
    assert source.hash_tags == ('#hash', '#tag')
    m_make_hash_tags.assert_called_once_with(('hash', 'tag'))

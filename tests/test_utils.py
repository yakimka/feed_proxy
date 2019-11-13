import pytest

from feed_proxy.parsers import RSSFeedParser
from feed_proxy.utils import load_class, AttrDict


def test_load_class():
    imported = load_class('feed_proxy.parsers.RSSFeedParser')
    assert imported is RSSFeedParser


def test_attr_dict():
    attr_dict = AttrDict()
    attr_dict.hello = 'world'

    assert attr_dict.hello == 'world'
    assert attr_dict['hello'] == 'world'


def test_attr_dict_has_no_key():
    attr_dict = AttrDict()

    pytest.raises(AttributeError, lambda: attr_dict.hello,
                  match=f"'AttrDict' object has no attribute 'hello'")

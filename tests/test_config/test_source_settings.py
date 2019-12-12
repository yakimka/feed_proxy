from collections import namedtuple

import pytest

from feed_proxy.config import SourceSettings
from feed_proxy.exceptions import ImproperlyConfigured


@pytest.fixture
def dict_source_settings(dict_source_settings):
    """Example source setting represented in dict
    Differs from overridden by the presence of a 'unexpected_key' key
    with 'dummy' value
    """

    dict_source_settings['unexpected_key'] = 'dummy'
    return dict_source_settings


SourceConfig = namedtuple('SourceConfig', 'name config')


@pytest.fixture
def source_config(config):
    """SourceConfig namedtuple with name "example source"
    and config['example source'] from "config" fixture
    """

    return SourceConfig('example source', config['example source'])


def test_unexpected_key_not_in_source(source_config):
    source_settings = SourceSettings(*source_config)

    assert not hasattr(source_settings, 'unexpected_key')


@pytest.mark.parametrize('field', [
    'disable_link_preview'
])
def test_get_send_kwargs(source_config, field):
    source_settings = SourceSettings(*source_config)
    send_kwargs = source_settings.get_send_kwargs()

    assert field in send_kwargs.keys()


def test_url_is_not_set(source_config):
    source_config.config['url'] = ''

    with pytest.raises(ImproperlyConfigured, match='You must specify url .*'):
        SourceSettings(*source_config)


def test_url_is_not_valid(source_config):
    source_config.config['url'] = 'example.com'

    with pytest.raises(ImproperlyConfigured, match='.* is not an URL'):
        SourceSettings(*source_config)


def test_nonexistent_parser_class(source_config):
    source_config.config['parser_class'] = 'WrongParser'

    with pytest.raises(ImproperlyConfigured, match='Wrong parser for "example source" section'):
        SourceSettings(*source_config)


def test_nonexistent_sender_class(source_config):
    source_config.config['sender_class'] = 'WrongSender'

    with pytest.raises(ImproperlyConfigured, match='Wrong sender for "example source" section'):
        SourceSettings(*source_config)

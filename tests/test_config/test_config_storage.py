import pytest

from feed_proxy.config import ConfigStorage, ConfigParser, SourceSettings
from feed_proxy.exceptions import ImproperlyConfigured


def test_config_storage_success(config):
    config_storage = ConfigStorage(config)

    assert len(config_storage.sources) > 0
    assert type(config_storage.sources['example source']) is SourceSettings


def test_empty_telegram_token_error(dict_config):
    dict_config['telegram']['token'] = ''

    config = ConfigParser().get_from_dict(dict_config)

    with pytest.raises(ImproperlyConfigured, match='You must specify token in telegram section'):
        ConfigStorage(config)


@pytest.fixture
def monkeypatch_load_class(monkeypatch):
    """
    Monkeypatch "utils.load_class" with function
    that return MockSender dummy class
    """
    def mock_load_class(*args):
        class MockSender:
            def __init__(self, *args, **kwargs):
                pass
        return MockSender
    monkeypatch.setattr('feed_proxy.config.load_class', mock_load_class)


def test_empty_telegram_token_not_raise_error_if_nobody_need_tg_parser(dict_config, monkeypatch_load_class):
    dict_config['example source']['sender_class'] = 'NotTelegram'
    dict_config['telegram']['token'] = ''

    config = ConfigParser().get_from_dict(dict_config)

    try:
        ConfigStorage(config)
    except ImproperlyConfigured:
        pytest.fail('Unexpected ImproperlyConfigured')


@pytest.mark.xfail
def test_config_has_not_telegram_token_error(dict_config, reason="need config refactoring"):
    """
    It is impossible now to validate an attribute which is not in the config
    need different config structure, like django serializers for example
    """
    del dict_config['telegram']['token']
    config = ConfigParser().get_from_dict(dict_config)

    with pytest.raises(ImproperlyConfigured, match='You must specify token in telegram section'):
        ConfigStorage(config)

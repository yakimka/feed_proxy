from feed_proxy.config import get_config_storage, ConfigStorage


def test_get_config_storage(mock_config_parser):
    config = get_config_storage()
    assert type(config) is ConfigStorage

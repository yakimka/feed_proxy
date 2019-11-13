import pytest

from feed_proxy.config import ConfigParser
from feed_proxy.exceptions import ImproperlyConfigured


@pytest.fixture
def config_parser(tmp_path):
    """Return ConfigParser instance with replaced
    "configfile_name" and "configfile_path" attributes with
    'test_config.ini' file name and tmp path
    """

    ConfigParser.configfile_name = 'test_config.ini'
    ConfigParser.configfile_path = tmp_path / ConfigParser.configfile_name

    return ConfigParser()


def test_exit_in_get_or_create_and_exit(config_parser):
    with pytest.raises(SystemExit):
        config_parser.get_or_create_and_exit()

    assert config_parser.configfile_path.exists()


def test_get_in_get_or_create_and_exit(config_parser):
    config_parser.create_example_configfile()

    config = config_parser.get_or_create_and_exit()

    assert all(k in config for k in ['DEFAULT', 'telegram', 'example source'])


def test_empty_config_in_get_or_create_and_exit(config_parser):
    config_parser.configfile_path.touch()

    with pytest.raises(ImproperlyConfigured, match='Check your config file'):
        config_parser.get_or_create_and_exit()


def test_get(config_parser):
    config_parser.create_example_configfile()

    config = config_parser.get()

    assert all(k in config for k in ['DEFAULT', 'telegram', 'example source'])


def test_get_from_dict(config):
    all(k in config for k in ['DEFAULT', 'telegram', 'example source'])


def test_create_example_configfile_and_exit(config_parser):
    config_parser.create_example_configfile()
    with open(config_parser.configfile_path, 'r') as configfile:
        config = configfile.read()
        assert '[DEFAULT]' in config
        assert '[telegram]' in config


@pytest.mark.parametrize('string,expected', [
    ('', []),
    ('some', ['some']),
    ('some some2', ['some', 'some2']),
    (' some some2 ', ['some', 'some2']),
])
def test_getlist(string, expected):
    assert ConfigParser.getlist(string) == expected


@pytest.mark.parametrize('string,expected', [
    ('{message}<br><br>{source_tags}', '{message}\n\n{source_tags}'),
    ('{message} <br> <br> {source_tags}', '{message} \n \n {source_tags}'),
])
def test_gettemplate(string, expected):
    assert ConfigParser.gettemplate(string) == expected

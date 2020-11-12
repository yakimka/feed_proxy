from unittest.mock import Mock, patch

import pytest

from feed_proxy import utils
from feed_proxy.parsers import rss_feed_posts_parser


def test_load_obj():
    imported = utils.load_obj('feed_proxy.parsers.rss_feed_posts_parser')
    assert imported is rss_feed_posts_parser


@pytest.fixture()
def mock_Config(mocker):
    return mocker.patch.object(utils, 'Config')


class TestMakeAlembicConfigFunc:
    def setup_method(self):
        self.cmd_opts = Mock()
        self.cmd_opts.config = 'conf.ini'
        self.cmd_opts.db_url = ''

    def test_make_config(self, mock_Config):
        config = utils.make_alembic_config(self.cmd_opts, '/base/path/')

        mock_Config.assert_called_once_with(
            file_=self.cmd_opts.config,
            ini_section=self.cmd_opts.name,
            cmd_opts=self.cmd_opts
        )
        assert config == mock_Config.return_value

    def test_config_path_make_absolute(self, mock_Config):
        self.cmd_opts.config = 'conf.ini'
        utils.make_alembic_config(self.cmd_opts, '/base/path/')

        assert self.cmd_opts.config == '/base/path/conf.ini'

    def test_config_path_already_absolute(self, mock_Config):
        self.cmd_opts.config = '/conf.ini'
        utils.make_alembic_config(self.cmd_opts, '/base/path/')

        assert self.cmd_opts.config == '/conf.ini'

    def test_alembic_location_make_absolute(self, mock_Config):
        mock_Config.return_value.get_main_option.return_value = 'env.py'
        config = utils.make_alembic_config(self.cmd_opts, '/base/path/')

        config.set_main_option.assert_called_once_with(
            'script_location',
            '/base/path/env.py'
        )

    def test_alembic_location_already_absolute(self, mock_Config):
        mock_Config.return_value.get_main_option.return_value = '/env.py'
        config = utils.make_alembic_config(self.cmd_opts, '/base/path/')

        for args, kwargs in config.set_main_option.call_args_list:
            assert args[0] != 'script_location'

    def test_set_db_url(self, mock_Config):
        self.cmd_opts.db_url = 'db.sqlite'
        config = utils.make_alembic_config(self.cmd_opts, '/base/path/')

        config.set_main_option.assert_called_with('sqlalchemy.url', 'db.sqlite')

    def test_wo_db_url(self, mock_Config):
        self.cmd_opts.db_url = ''
        config = utils.make_alembic_config(self.cmd_opts, '/base/path/')

        for args, kwargs in config.set_main_option.call_args_list:
            assert args[0] != 'sqlalchemy.url'


def test_make_hash_tags():
    tags = (
        'таг с АББРЕВИАТУРОЙ',
        'таг с символом отличным от нижнего подчеркивания!',
        'таг  с несколькими.-=>пробелами',
        'таг с украинскими символами єїґіІЄЇҐ',
        'таг с символом ёЁ',
        'Таг с Заглавными Буквами',
        'english tag',
    )

    assert utils.make_hash_tags(tags) == [
        '#таг_с_аббревиатурой',
        '#таг_с_символом_отличным_от_нижнего_подчеркивания_',
        '#таг_с_несколькими_пробелами',
        '#таг_с_украинскими_символами_єїґіієїґ',
        '#таг_с_символом_ёё',
        '#таг_с_заглавными_буквами',
        '#english_tag',
    ]


def test_make_hash_tags_empty_iterable():
    assert utils.make_hash_tags(tuple()) == []


@patch.object(utils.os.path, 'exists')
def test_validate_file(m_exists):
    assert utils.validate_file('parser', '/some/path') == '/some/path'
    m_exists.assert_called_once_with('/some/path')


@patch.object(utils.os.path, 'exists')
def test_validate_file_not_exists(m_exists):
    parser = Mock()
    m_exists.return_value = False

    utils.validate_file(parser, '/some/path')

    parser.error.assert_called_once_with("The file '/some/path' does not exist!")

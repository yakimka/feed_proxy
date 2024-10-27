from unittest.mock import patch

import pytest

from feed_proxy import conf

reader_class = conf.ConfigReader


@pytest.mark.parametrize('string,expected', [
    ('', tuple()),
    ('cookie', ('cookie',)),
    ('icecream chocolate', ('icecream', 'chocolate')),
    (' hop hey ', ('hop', 'hey')),
    ('поп  корн', ('поп', 'корн')),
])
def test_convert_tuple(string, expected):
    assert reader_class.convert_tuple(string) == expected


@pytest.mark.parametrize('string,expected', [
    ('{message}<br><br>{source_tags}', '{message}\n\n{source_tags}'),
    ('{message} <br> <br> {source_tags}', '{message} \n \n {source_tags}'),
])
def test_convert_template(string, expected):
    assert reader_class.convert_template(string) == expected


@pytest.mark.parametrize('string,expected', [
    ('tag1', ('tag1',)),
    ('tag 1', ('tag 1',)),
    ('tag1,tag2', ('tag1', 'tag2')),
    ('tag1,tag 2', ('tag1', 'tag 2')),
    ('таг с кириллицей', ('таг с кириллицей',)),
    ('TAG with Uppercase', ('tag with uppercase',)),
])
def test_convert_excludepostbytags(string, expected):
    assert reader_class.convert_excludepostbytags(string) == expected


@pytest.fixture()
def converters():
    """
    Expected ConfigReader converters
    """
    return {
        'tuple': reader_class.convert_tuple,
        'template': reader_class.convert_template,
        'excludepostbytags': reader_class.convert_excludepostbytags,
    }


def test_get_converters(converters):
    assert reader_class.get_converters() == converters


@pytest.fixture()
def kwargs(converters):
    """
    Expected ConfigReader kwargs
    """
    return {'converters': converters}


def test_get_parser_kwargs(kwargs):
    assert reader_class.get_parser_kwargs() == kwargs


def test_get_parser_kwargs_empty_converters(mocker, kwargs):
    mocker.patch.object(reader_class, 'get_converters', return_value={})

    assert reader_class.get_parser_kwargs() == {}


@patch.object(conf.configparser, 'ConfigParser', return_value=42)
def test_create_parser(mock_ConfigParser, kwargs):
    assert reader_class.create_parser() == 42
    mock_ConfigParser.assert_called_once_with(**kwargs)


@patch.object(reader_class, 'create_parser')
def test_read_from_file(mock_create_parser):
    mock_parser = mock_create_parser.return_value
    assert reader_class.read_from_file('/path') == mock_parser
    mock_parser.read.assert_called_once_with('/path')

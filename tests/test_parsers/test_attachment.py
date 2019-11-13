import os

import pytest

from feed_proxy.exceptions import FeedProxyException
from feed_proxy.parsers import Attachment


@pytest.mark.parametrize('field,obj', [
    ('url', 'mp3_enclosure'),
    ('type', 'mp3_enclosure'),
    ('author', 'post'),
    ('title', 'post'),
])
def test_fields(mp3_attachment, post, mp3_enclosure, field, obj):
    assert getattr(mp3_attachment, field) == getattr(locals()[obj], field)


@pytest.fixture
def attachment_factory(post, mp3_enclosure):
    """Attachment factory which takes parameters:
    url - enclosure url
    type - enclosure type

    By default create Attachment from "mp3_enclosure"
    """

    def factory(url=None, type=None):
        if url is not None:
            mp3_enclosure.url = url
        if type is not None:
            mp3_enclosure.type = type

        return Attachment(mp3_enclosure, post=post)

    return factory


@pytest.mark.parametrize('url1,url2,expected', [
    ('http://example.com', 'http://example.com', True),
    ('http://example.com', 'http://hello.com', False),
])
def test_compare(attachment_factory, url1, url2, expected):
    attachment1 = attachment_factory(url1)
    attachment2 = attachment_factory(url2)

    assert (attachment1 == attachment2) is expected


@pytest.mark.parametrize('obj,expected', [
    (123, False),
    ('dummy', False),
    (object(), False),
    ({}, False),
])
def test_compare_with_another_types(mp3_attachment, obj, expected):
    assert (mp3_attachment == obj) is expected


def test_get_file_info(mp3_attachment, mock_get_file_info_51mb):
    size, direct_url, file_type = mp3_attachment.get_file_info()

    assert size == 51
    assert direct_url == mp3_attachment.url
    assert file_type == mp3_attachment.type


def test_get_file_info_with_error_code_from_server(mp3_attachment, requests_mock):
    requests_mock.head(mp3_attachment.url, status_code=400)

    with pytest.raises(FeedProxyException, match=f'Could not retrieve data from {mp3_attachment.url}'):
        mp3_attachment.get_file_info()


def test_get_file_info_with_connection_error(mp3_attachment, mock_connection_error):
    with pytest.raises(FeedProxyException, match=f'Could not retrieve data from {mp3_attachment.url}'):
        mp3_attachment.get_file_info()


def test_download(mp3_attachment, mock_download_file_url):
    mp3_attachment.download()
    with open(mp3_attachment.file.name, 'r') as f:
        downloaded = f.read()

    assert downloaded == 'file content'


def test_download_with_connection_error(mp3_attachment, mock_connection_error):
    with pytest.raises(FeedProxyException, match=f'Could not download file from {mp3_attachment.url}'):
        mp3_attachment.download()

    assert mp3_attachment.file is None


def test_delete(mp3_attachment, mock_download_file_url):
    mp3_attachment.download()
    file_path = mp3_attachment.file.name

    mp3_attachment.delete()

    assert not os.path.exists(file_path)
    assert mp3_attachment.file is None


@pytest.mark.parametrize('file_type,expected', [
    ('audio', True),
    ('audio/mp3', True),
    ('audio/aac', True),
    ('document', False),
    ('document/xls', False),
])
def test_is_audio(attachment_factory, file_type, expected):
    attachment = attachment_factory(type=file_type)

    assert attachment.is_audio() is expected

from datetime import datetime
from unittest.mock import patch

import pytest

from feed_proxy import schema


@pytest.fixture()
def audio_attachment():
    return schema.Attachment(
        href='http://localhost:45432/song.mp3',
        type='audio/mpeg',
        length=21652106
    )


@pytest.fixture()
def other_audio_attachment():
    return schema.Attachment(
        href='http://localhost:45432/song2.mp3',
        type='audio/mpeg',
        length=21652106
    )


@pytest.fixture()
def post_data(source, audio_attachment):
    return {
        'author': 'asvetlov',
        'authors': (schema.Author(name='asvetlov'),),
        'source': source,
        'id': 'tag:github.com,2008:Repository/13258039/v3.7.0b0',
        'url': 'https://github.com/aio-libs/aiohttp/releases/tag/v3.7.0b0',
        'summary': '<p>Release 3.7.0b0</p>',
        'title': 'v3.7.0b0',
        'tags': ('post_hash', 'post_tag'),
        'attachments': (
            audio_attachment,
            schema.Attachment(
                href='http://localhost:45432/archive.zip',
                type='application/zip',
                length=51652106
            )
        ),
        'published': datetime(2020, 10, 21, 19, 54, 4)
    }


@pytest.fixture()
def post(post_data):
    return schema.Post(**post_data)


def test_has_audio(post):
    assert post.has_audio() is True


def test_has_audio_on_empty_attachments(post_data):
    post_data['attachments'] = tuple()
    post = schema.Post(**post_data)

    assert post.has_audio() is False


def test_has_audio_false(post_data):
    post_data['attachments'] = (post_data['attachments'][1],)
    post = schema.Post(**post_data)

    assert post.has_audio() is False


def test_audio(post, audio_attachment):
    assert post.audio == audio_attachment


def test_audio_on_empty_attachments(post_data):
    post_data['attachments'] = tuple()
    post = schema.Post(**post_data)

    assert post.audio is None


def test_audio_first_audio(post_data, audio_attachment, other_audio_attachment):
    post_data['attachments'] = (audio_attachment, other_audio_attachment)
    post = schema.Post(**post_data)

    assert post.audio == audio_attachment


@patch.object(schema, 'make_hash_tags', return_value=['#hash', '#tag'])
def test_hash_tags(m_make_hash_tags, post):
    assert post.hash_tags == ('#hash', '#tag')
    m_make_hash_tags.assert_called_once_with(('post_hash', 'post_tag'))


def test_message_text(post):
    assert post.message_text == (
        '<a href="https://github.com/aio-libs/aiohttp/releases/tag/v3.7.0b0">v3.7.0b0</a>'
        '\n\n#hash #tag #post_hash #post_tag'
    )
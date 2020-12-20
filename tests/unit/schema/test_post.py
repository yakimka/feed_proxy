from datetime import datetime
from unittest.mock import patch

import pytest

from feed_proxy import schema
from feed_proxy.schema import Post, Source


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
        'author': 'yakimka',
        'authors': (schema.Author(name='yakimka'),),
        'source': source,
        'id': 'audio_gt_20mb',
        'url': 'https://github.com/yakimka/feed_proxy/releases/tag/95',
        'summary': 'Lorem ipsum dolor sit amet, consectetur adipisicing.',
        'title': 'feed_proxy 95 release',
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


def test_message_text(source_data, post_data):
    source_data['post_template'] = ('{all_tags} {post_tags} {source_tags}\n'
                                    '{source_name} {author} {url} {summary} {title} {published}')
    post_data['source'] = Source(**source_data)
    post = Post(**post_data)

    assert post.message_text == (
        '#hash #tag #post_hash #post_tag #post_hash #post_tag #hash #tag\nfeed_proxy releases'
        ' yakimka https://github.com/yakimka/feed_proxy/releases/tag/95'
        ' Lorem ipsum dolor sit amet, consectetur adipisicing. feed_proxy 95 release'
        ' 21-10-2020 19:54:04'
    )


def test_message_text_when_published_not_parsed(source_data, post_data):
    source_data['post_template'] = '{source_name} {published}'
    post_data['source'] = Source(**source_data)
    post_data['published'] = None
    post = Post(**post_data)

    assert post.message_text == 'feed_proxy releases'

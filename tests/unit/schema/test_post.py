from unittest.mock import patch

from feed_proxy import schema


def test_has_audio(factory):
    post = factory.post()

    assert post.has_audio() is True


def test_has_audio_on_empty_attachments(factory):
    post = factory.post(attachments=tuple())

    assert post.has_audio() is False


def test_has_audio_false(factory):
    post = factory.post(attachments=(factory.zip_attachment(),))

    assert post.has_audio() is False


def test_audio(factory):
    post = factory.post()

    assert post.audio == factory.audio_attachment()


def test_audio_on_empty_attachments(factory):
    post = factory.post(attachments=tuple())

    assert post.audio is None


def test_audio_first_audio(factory):
    post = factory.post(
        attachments=(factory.audio_attachment(), factory.audio_attachment('song2.mp3')))

    assert post.audio == factory.audio_attachment()


@patch.object(schema, 'make_hash_tags', return_value=['#hash', '#tag'])
def test_hash_tags(m_make_hash_tags, factory):
    post = factory.post(tags=('post_hash', 'post_tag'))

    assert post.hash_tags == ('#hash', '#tag')
    m_make_hash_tags.assert_called_once_with(('post_hash', 'post_tag'))


def test_message_text(factory):
    source = factory.source(post_template=(
        '{all_tags} {post_tags} {source_tags}\n'
        '{source_name} {author} {url} {summary} {title} {published}'
    ))
    post = factory.post(source=source)

    assert post.message_text == (
        '#hash #tag #post_hash #post_tag #post_hash #post_tag #hash #tag\nfeed_proxy releases'
        ' yakimka https://github.com/yakimka/feed_proxy/releases/tag/95'
        ' Lorem ipsum dolor sit amet, consectetur adipisicing. feed_proxy 95 release'
        ' 21-10-2020 19:54:04'
    )


def test_message_text_when_published_not_parsed(factory):
    source = factory.source(post_template='{source_name} {published}')
    post = factory.post(source=source, published=None)

    assert post.message_text == 'feed_proxy releases'

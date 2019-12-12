import pytest

from feed_proxy.parsers import Attachment


@pytest.mark.parametrize('field', [
    'author',
    'enclosures',
    'id',
    'link',
    'published',
    'summary',
    'title',
])
def test_fields(raw_post, post, field):
    assert getattr(post, field) == getattr(raw_post, field)


@pytest.mark.parametrize('field,obj', [
    ('author', 'post'),
    ('title', 'post'),
    ('type', 'mp3_enclosure'),
    ('url', 'mp3_enclosure'),
])
def test_attachments(post, mp3_enclosure, field, obj):
    attachment = post.attachments[0]

    assert getattr(attachment, field) == getattr(locals()[obj], field)


def test_attachment_is_not_downloaded(post):
    assert post.attachments[0].file is None


def test_tags(post):
    assert post.tags == ['python', 'django']


def test_url_equal_to_link(post):
    assert post.link == post.url


@pytest.fixture
def expected_to_dict(raw_post, mp3_enclosure):
    """Dict created from "raw_post" and "mp3_enclosure" fixtures
    which is expected to receive from "to_dict" method of Post from "post" fixture
    """

    expected = dict(raw_post)
    expected['tags'] = ['python', 'django']
    expected['url'] = expected['link']
    expected['attachments'] = [Attachment(mp3_enclosure, post=raw_post)]
    return expected


def test_to_dict(post, expected_to_dict):
    assert post.to_dict() == expected_to_dict

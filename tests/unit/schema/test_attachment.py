import pytest

from feed_proxy.schema import Attachment


@pytest.mark.parametrize('type_,expected', [
    ('audio/mpeg', True),
    ('audio/mp3', True),
    ('audio/aac', True),
    ('audio/ogg', True),
    ('video/3gpp', False),
    ('application/zip', False),
])
def test_is_audio(type_, expected):
    attachment = Attachment(
        href='http://localhost:45432/some_file',
        type=type_,
        length=42
    )

    assert attachment.is_audio is expected


def test_guess_extension_from_type():
    attachment = Attachment(href='http://localhost', type='audio/mpeg', length=0)

    assert attachment.guess_extension() == '.mp3'


def test_guess_extension_from_href():
    attachment = Attachment(href='http://localhost/audio.some.mp4', type='audio/dummy', length=0)

    assert attachment.guess_extension() == '.mp4'


def test_cant_guess_extension():
    attachment = Attachment(href='http://localhost/audio', type='audio/dummy', length=0)

    assert attachment.guess_extension() is None

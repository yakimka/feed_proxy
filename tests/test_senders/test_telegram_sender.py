from unittest import mock

import pytest

from feed_proxy.exceptions import FeedProxyException


CHAT_ID = -1001234567890
MESSAGE = 'message_text'
TOKEN = 'tg_bot_token'


def test_token_is_set_from_config_if_not_passed(tg_sender, config_storage):
    tg_sender.mocked_bot.assert_called_once_with(config_storage.data['telegram']['token'])


@pytest.fixture
def tg_sender_with_passed_token(request, mocked_tg_sender_class):
    """Return "TelegramSender" instance.
    "chat_id" "message" and "token" params are taken
    from the module variables "CHAT_ID" "MESSAGE" and "TOKEN"
    """

    chat_id = getattr(request.module, 'CHAT_ID')
    message = getattr(request.module, 'MESSAGE')
    token = getattr(request.module, 'TOKEN')
    return mocked_tg_sender_class(chat_id, message, token=token)


def test_token_is_set_from_parameters(tg_sender_with_passed_token, config_storage):
    tg_sender_with_passed_token.mocked_bot.assert_called_once_with(TOKEN)


@pytest.fixture
def tg_sender_with_attachments(request, post_factory, mocked_tg_sender_class,
                               jpeg_enclosure, mp3_enclosure, aac_enclosure, mp4_enclosure):
    """Return "TelegramSender" instance with attachments.
    List with attachments can be passed with "request.params".

    "chat_id" and "message" params are taken
    from the module variables "CHAT_ID" and "MESSAGE"
    """

    enclosures = request.param

    locals_ = locals()
    enclosures = [locals_[obj] for obj in enclosures]
    post = post_factory({'enclosures': enclosures})

    chat_id = getattr(request.module, 'CHAT_ID')
    message = getattr(request.module, 'MESSAGE')

    return mocked_tg_sender_class(chat_id, message, attachments=post.attachments)


@pytest.mark.parametrize('tg_sender_with_attachments,expected', [
    (['jpeg_enclosure', 'aac_enclosure', 'mp4_enclosure'], 'audio/aac'),
    (['aac_enclosure', 'mp3_enclosure'], 'audio/aac'),
    (['mp3_enclosure', 'mp4_enclosure'], 'audio/mp3'),
    (['mp3_enclosure'], 'audio/mp3'),
    (['jpeg_enclosure', 'mp4_enclosure'], None),
], indirect=['tg_sender_with_attachments'])
def test_audio(tg_sender_with_attachments, expected):
    if expected is None:
        assert tg_sender_with_attachments.audio is None
    else:
        assert tg_sender_with_attachments.audio.type == expected


def test_send_message(tg_sender):
    tg_sender.send_message()

    check_message_sent(tg_sender, CHAT_ID, MESSAGE)


def check_message_sent(tg_sender, chat_id=None, message=None):
    __tracebackhide__ = True

    if chat_id is None:
        chat_id = tg_sender.chat_id
    if message is None:
        message = tg_sender.message

    tg_sender.bot.send_message.assert_called_once_with(
        chat_id,
        message,
        parse_mode='html',
        disable_web_page_preview=tg_sender.disable_link_preview
    )


@pytest.mark.parametrize('tags,expected', [
    (['python', 'django', 'pytest'], '#python #django #pytest'),
    ([' python', 'django ', ' pytest '], '#python #django #pytest'),
])
def test_tags_to_string(tg_sender, tags, expected):
    assert tg_sender.tags_to_string(tags) == expected


@pytest.fixture
def tg_sender_with_audio(request, mocked_tg_sender_class, mp3_attachment):
    """Return "TelegramSender" instance with mp3 attachment.
    "chat_id" and "message" params are taken
    from the module variables "CHAT_ID" and "MESSAGE"
    """

    chat_id = getattr(request.module, 'CHAT_ID')
    message = getattr(request.module, 'MESSAGE')
    return mocked_tg_sender_class(chat_id, message, attachments=[mp3_attachment])


def test_send_audio_where_no_audio(tg_sender, requests_mock):
    with pytest.raises(FeedProxyException, match='No audio to send'):
        tg_sender.send_audio()


def test_send_audio_too_big_file(tg_sender_with_audio, mock_get_file_info_51mb):
    with pytest.raises(FeedProxyException,
                       match='Files larger than 50MB can\'t be sent through Telegram Bot API'):
        tg_sender_with_audio.send_audio()


def test_send_audio_too_big_for_download_from_url(tg_sender_with_audio,
                                                  mock_get_file_info_21mb,
                                                  mock_download_file_url):
    tg_sender_with_audio.send_audio()

    check_is_audio_sent(tg_sender_with_audio, CHAT_ID, MESSAGE, from_file=True)


def check_is_audio_sent(tg_sender, chat_id=None, caption=None, from_file=False):
    __tracebackhide__ = True

    if chat_id is None:
        chat_id = tg_sender.chat_id
    if caption is None:
        caption = tg_sender.message
    file_or_url = mock.ANY if from_file else tg_sender.audio.url

    if from_file:
        assert tg_sender.audio.file is not None
    else:
        assert tg_sender.audio.file is None

    tg_sender.bot.send_audio.assert_called_once()
    tg_sender.bot.send_audio.assert_has_calls([
        mock.call(chat_id,
                  file_or_url,
                  caption=caption,
                  performer=tg_sender.audio.author,
                  title=tg_sender.audio.title,
                  parse_mode='html',
                  timeout=mock.ANY)
    ])


def test_send_audio_download_from_url(tg_sender_with_audio,
                                      mock_get_file_info_1mb):
    tg_sender_with_audio.send_audio()

    check_is_audio_sent(tg_sender_with_audio, CHAT_ID, caption=MESSAGE)


def test_send_without_audio(tg_sender):
    tg_sender.send()

    tg_sender.bot.send_message.assert_called_once()


def test_send_with_audio(tg_sender_with_audio, mock_get_file_info_1mb):
    tg_sender_with_audio.send()

    tg_sender_with_audio.bot.send_audio.assert_called_once()


def test_send_audio_with_big_caption(tg_sender_with_audio,
                                     mock_get_file_info_1mb):
    message = ''.join('a' for _ in range(1025))
    tg_sender_with_audio.message = message
    tg_sender_with_audio.send_audio()

    check_is_audio_sent(tg_sender_with_audio, CHAT_ID, caption='')
    check_is_replied_to_message(tg_sender_with_audio,
                                tg_sender_with_audio.bot.send_audio.return_value, message)


def check_is_replied_to_message(tg_sender, message_obj, message=None):
    if message is None:
        message = tg_sender.message

    tg_sender.bot.reply_to.assert_called_once()
    tg_sender.bot.reply_to.assert_has_calls([
        mock.call(message_obj,
                  message,
                  parse_mode='html',
                  disable_web_page_preview=tg_sender.disable_link_preview)
    ])

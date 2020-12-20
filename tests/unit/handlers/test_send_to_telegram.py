from typing import List
from unittest.mock import ANY, Mock, call, patch

import pytest

from feed_proxy import handlers

handler_class = handlers.SendToTelegram


@pytest.fixture()
def handler(migrated_sqlite_connection):
    with patch.object(handlers, 'Bot'):
        handler_ = handler_class(migrated_sqlite_connection)
        handler_.pause_between_send = 0.1
        return handler_


def test_init(handler, migrated_sqlite_connection):
    assert handler.bot
    assert handler.proxy_bot
    assert handler.conn is migrated_sqlite_connection


@pytest.fixture()
def text_and_audio_posts() -> List[Mock]:
    post_with_audio = Mock()
    post_with_audio.has_audio.return_value = True
    post_wo_audio = Mock()
    post_wo_audio.has_audio.return_value = False
    return [post_wo_audio, post_with_audio]


@patch.object(handlers.schema, 'create_processed')
@patch.object(handlers.SendToTelegram, 'send_audio')
@patch.object(handlers.SendToTelegram, 'send_message')
def test_call(m_send_message, m_send_audio, m_create_processed, handler, text_and_audio_posts):
    post_wo_audio, post_with_audio = text_and_audio_posts

    res = handler(text_and_audio_posts)

    assert res == text_and_audio_posts
    m_send_message.assert_called_once_with(post_wo_audio)
    m_send_audio.assert_called_once_with(post_with_audio)


@patch.object(handlers.schema, 'create_processed')
@patch.object(handlers.SendToTelegram, 'send_audio')
@patch.object(handlers.SendToTelegram, 'send_message')
def test_call_create_processed(
        m_send_message, m_send_audio, m_create_processed, handler, text_and_audio_posts
):
    post_wo_audio, post_with_audio = text_and_audio_posts

    handler(text_and_audio_posts)

    assert m_create_processed.call_count == 2
    m_create_processed.assert_has_calls([
        call(handler.conn, post_wo_audio),
        call(handler.conn, post_with_audio)
    ], any_order=True)


@patch.object(handlers.schema, 'create_processed')
@patch.object(handlers.SendToTelegram, 'send_audio')
@patch.object(handlers.SendToTelegram, 'send_message')
def test_call_not_create_processed_if_error(
        m_send_message, m_send_audio, m_create_processed, handler, text_and_audio_posts
):
    post_wo_audio, post_with_audio = text_and_audio_posts

    m_send_audio.side_effect = IOError

    handler(text_and_audio_posts)

    m_send_message.assert_called_once_with(post_wo_audio)
    m_create_processed.assert_called_once_with(handler.conn, post_wo_audio)


@patch.object(handlers.SendToTelegram, 'send_audio')
def test_call_log_error_when_sending(
        m_send_audio, handler, posts, caplog
):
    m_send_audio.side_effect = IOError('Connection error =(')

    handler([posts.audio_gt_20mb])

    assert caplog.records[0].levelname == 'ERROR'
    assert str(posts.audio_gt_20mb) in caplog.text
    assert 'Connection error =(' in caplog.text


@patch.object(handlers.SendToTelegram, 'send_audio')
@patch.object(handlers.SendToTelegram, 'send_message')
def test_call_empty_posts(m_send_message, m_send_audio, handler):
    res = handler([])

    assert res == []
    m_send_message.assert_not_called()
    m_send_audio.assert_not_called()


def test_send_message(handler, posts):
    post = posts.regular
    handler.send_message(post)

    handler.bot.send_message.assert_called_once_with(
        chat_id='-1001234567890',
        disable_web_page_preview=True,
        parse_mode='HTML',
        text=post.message_text
    )


def test_download_file(mock_download_file, handler, posts):
    post = posts.audio_gt_20mb

    res = handler.download_file(post.audio)

    with open(res, 'r') as fp:
        assert fp.read() == 'file content'


def test_send_audio_when_file_less_then_20mb(handler, posts):
    post = posts.audio_lt_20mb

    handler.send_audio(post)

    handler.bot.send_audio.assert_called_once_with(
        chat_id='-1001234567890',
        audio='http://localhost:45432/song.mp3',
        performer='yakimka',
        title='feed_proxy 94 release',
        parse_mode='HTML',
        caption=post.message_text,
    )


@patch.object(handlers, 'open')
@patch.object(handlers.SendToTelegram, 'download_file', return_value='/mtmp/mfile')
def test_send_audio_when_file_great_then_20mb(m_download_file, m_open, handler, posts):
    post = posts.audio_gt_20mb

    handler.send_audio(post)

    m_download_file.assert_called_once_with(post.audio)
    m_open.assert_called_once_with('/mtmp/mfile', 'rb')
    handler.proxy_bot.send_audio.assert_called_once_with(
        audio=m_open().__enter__(),
        timeout=ANY,
        chat_id='-1001234567890',
        performer='yakimka',
        title='feed_proxy 95 release',
        parse_mode='HTML',
        caption=post.message_text,
    )


@patch.object(handlers, 'open')
@patch.object(handlers.SendToTelegram, 'download_file', return_value='/mtmp/mfile')
def test_send_audio_when_file_size_is_zero(m_download_file, m_open, handler, posts):
    post = posts.audio_0b

    handler.send_audio(post)

    m_download_file.assert_called_once_with(post.audio)
    m_open.assert_called_once_with('/mtmp/mfile', 'rb')
    handler.proxy_bot.send_audio.assert_called_once_with(
        audio=m_open().__enter__(),
        timeout=ANY,
        chat_id='-1001234567890',
        performer='yakimka',
        title='feed_proxy 93 release',
        parse_mode='HTML',
        caption=post.message_text,
    )

import logging
import tempfile
from collections import OrderedDict
from time import sleep
from typing import List

import requests
from sqlalchemy.engine import Connection
from telegram import Bot

from feed_proxy.conf import settings
from feed_proxy.db import schema
from feed_proxy.schema import Attachment, Post

logger = logging.getLogger(__name__)


def make_source_mapping(posts: List[Post]) -> dict:
    result = OrderedDict()
    for post in posts:
        result.setdefault(post.source, []).append(post)
    return result


class FilterNewSource:
    def __init__(self, conn: Connection):
        self.conn = conn

    def __call__(self, parsed_posts: List[Post]) -> List[Post]:
        without_new = []

        source_mapping = make_source_mapping(parsed_posts)
        for source, posts in source_mapping.items():
            if schema.is_new_source(self.conn, source):
                # older posts will be wrote first
                schema.create_processed(self.conn, posts[:settings.NUM_MESSAGES_TO_STORE][::-1])
            else:
                without_new.extend(posts)
        return without_new


class FilterProcessed:
    def __init__(self, conn: Connection):
        self.conn = conn

    def __call__(self, parsed_posts: List[Post]) -> List[Post]:
        not_processed = []

        source_mapping = make_source_mapping(parsed_posts)
        for source, posts in source_mapping.items():
            for post in posts:  # posts is always list with at least 1 element
                if schema.is_post_processed(self.conn, post):
                    if source.check_processed_until_first_match:
                        break
                    else:
                        continue  # pragma: no cover https://github.com/nedbat/coveragepy/issues/198
                not_processed.append(post)
        return not_processed


class SendToTelegram:
    MAX_CAPTION_LENGTH = 1024
    MAX_FILESIZE_DOWNLOAD = 20000000
    MAX_FILESIZE_UPLOAD = 50000000
    MAX_MESSAGES_PER_MINUTE_PER_GROUP = 20
    MAX_MESSAGES_PER_SECOND = 30
    MAX_MESSAGES_PER_SECOND_PER_CHAT = 1
    MAX_MESSAGE_LENGTH = 4096
    MAX_MESSAGE_LENGTH_IN_GRAPH = 65536

    pause_between_send = 60 / MAX_MESSAGES_PER_MINUTE_PER_GROUP  # seconds

    def __init__(self, conn: Connection):
        self.conn = conn

        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.proxy_bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN
        )
        self.proxy_bot.base_url = settings.PROXY_BOT_URL

    def __call__(self, parsed_posts: List[Post]) -> List[Post]:
        for post in reversed(parsed_posts):
            try:
                if post.has_audio():
                    self.send_audio(post)
                else:
                    self.send_message(post)
            # TODO RetryAfter
            except Exception:
                logger.exception(f"Can't send post: {post}")
                continue

            schema.create_processed(self.conn, post)
            sleep(self.pause_between_send)
        return parsed_posts

    def send_message(self, post: Post) -> None:
        self.bot.send_message(
            chat_id=post.source.receiver,
            text=post.message_text,
            parse_mode='HTML',
            disable_web_page_preview=post.source.disable_link_preview,
        )

    def send_audio(self, post: Post):
        message_data = {
            'chat_id': post.source.receiver,
            'performer': post.author,
            'title': post.title,
            'parse_mode': 'HTML',
            'caption': post.message_text,
        }

        if post.audio.length and post.audio.length < self.MAX_FILESIZE_DOWNLOAD:
            self.bot.send_audio(
                audio=post.audio.href,
                **message_data
            )
        else:
            audio_path = self.download_file(post.audio)
            with open(audio_path, 'rb') as fp:
                try:
                    self.proxy_bot.send_audio(
                        audio=fp,
                        timeout=300,
                        **message_data
                    )
                # tg_upload_proxy return response in unsupported with client format
                except KeyError:
                    pass

    @classmethod
    def download_file(cls, attachment: Attachment) -> str:
        res = requests.get(attachment.href, allow_redirects=True)
        with tempfile.NamedTemporaryFile(
                suffix=attachment.guess_extension(), delete=False) as file:
            file.write(res.content)
        return file.name

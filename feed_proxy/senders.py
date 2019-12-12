import telebot

from feed_proxy.config import get_config_storage
from feed_proxy.exceptions import FeedProxyException
from feed_proxy.utils import class_logger


class TelegramSender:
    MAX_CAPTION_SIZE = 1024
    MAX_FILE_SIZE = 50
    MAX_FILE_SIZE_FOR_URL = 20

    def __init__(self, chat_id, message, attachments=None, disable_link_preview=False, token=None):
        self.logger = class_logger(__name__, self.__class__.__name__)

        if token is None:
            token = get_config_storage().data['telegram']['token']
        if attachments is None:
            attachments = []
        self.bot = telebot.TeleBot(token)
        self.chat_id = chat_id
        self.message = message
        self.attachments = attachments
        self.audio = self._get_audio()
        self.disable_link_preview = disable_link_preview

    def _get_audio(self):
        for attachment in self.attachments:
            if attachment.is_audio():
                return attachment

        return None

    def send(self):
        try:
            self.send_audio()
            return
        except FeedProxyException:
            pass

        self.send_message()

    def send_audio(self):
        try:
            file_size, *_ = self.audio.get_file_info()
        except AttributeError:
            msg = 'No audio to send'
            self.logger.error(msg)
            raise FeedProxyException(msg)

        if file_size > self.MAX_FILE_SIZE:
            msg = f'Files larger than {self.MAX_FILE_SIZE}MB can\'t be sent through Telegram Bot API'
            self.logger.error(msg)
            raise FeedProxyException(msg)

        if file_size > self.MAX_FILE_SIZE_FOR_URL:
            self.audio.download()
            with open(self.audio.file.name, 'rb') as file:
                self._send_audio_with_message(file)
        else:
            self._send_audio_with_message(self.audio.url)

    def _send_audio_with_message(self, file_or_url):
        caption = self.message if len(self.message) < self.MAX_CAPTION_SIZE else ''

        message = self.bot.send_audio(self.chat_id,
                                      file_or_url,
                                      caption=caption,
                                      performer=self.audio.author,
                                      title=self.audio.title,
                                      parse_mode='html',
                                      timeout=30)

        if not caption:
            self.logger.warning('Caption too long, sending as a reply message')
            self._reply_to_message(message)

    def _reply_to_message(self, message):
        self.bot.reply_to(message,
                          self.message,
                          parse_mode='html',
                          disable_web_page_preview=self.disable_link_preview)

    def send_message(self):
        self.bot.send_message(self.chat_id, self.message, parse_mode='html',
                              disable_web_page_preview=self.disable_link_preview)

    @classmethod
    def tags_to_string(cls, tags):
        return ' '.join([f'#{tag.strip()}' for tag in tags])

# TODO exceptions
# telebot.apihelper.ApiException
# requests.exceptions.ConnectionError

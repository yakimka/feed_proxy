import configparser
import os
import sys
from collections import namedtuple
from functools import lru_cache
from urllib.parse import urlparse

from feed_proxy.exceptions import ImproperlyConfigured
from feed_proxy.utils import load_class

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSAGES_STORED = 5


@lru_cache()
def get_config_storage():
    config_parser = ConfigParser()
    config_storage = ConfigStorage(config_parser.get_or_create_and_exit())
    return config_storage


class ConfigStorage:
    sections = ['telegram']

    def __init__(self, config):
        self.sources = self._get_sources_settings(config)

        self.messages_stored = MESSAGES_STORED

        self.data = self.validate(config)

    def validate(self, data):
        attrs = {}
        for section in data:
            if section in self.sections:
                for key, value in data[section].items():
                    validate_method = getattr(self, f'validate_{section}_{key}', None)
                    if validate_method:
                        value = validate_method(value)
                    attrs.setdefault(section, {})[key] = value
            else:
                attrs[section] = data[section]

        return attrs

    @classmethod
    def _get_sources_settings(cls, config):
        sources = {}
        for source_name in config.sections():
            if source_name not in cls.sections:
                sources[source_name] = SourceSettings(source_name, config[source_name])

        return sources

    def validate_telegram_token(self, token):
        if not token and self._is_any_source_need_telegram_sender():
            raise ImproperlyConfigured(f'You must specify token in telegram section')

        return token

    def _is_any_source_need_telegram_sender(self):
        for source in self.sources.values():
            if source.sender_class is load_class('feed_proxy.senders.TelegramSender'):
                return True
        return False


class ConfigParser:
    configfile_name = 'config.ini'
    configfile_path = os.path.join(BASE_DIR, configfile_name)

    @classmethod
    def get_or_create_and_exit(cls):
        if not os.path.exists(cls.configfile_path):
            cls.create_example_configfile()
            sys.exit()

        config = cls.get()
        if not config.sections():
            raise ImproperlyConfigured('Check your config file')

        return config

    @classmethod
    def get(cls):
        config = cls._get_config_object()
        config.read(cls.configfile_path)

        return config

    @classmethod
    def get_from_dict(cls, dict):
        config = cls._get_config_object()
        config.read_dict(dict)

        return config

    @classmethod
    def _get_config_object(cls):
        return configparser.ConfigParser(converters={
            'list': cls.getlist,
            'template': cls.gettemplate
        })

    @staticmethod
    def getlist(val):
        return list(filter(None, val.split(' ')))

    @staticmethod
    def gettemplate(val):
        return val.replace('<br>', '\n')

    @classmethod
    def create_example_configfile(cls):
        config = configparser.ConfigParser(allow_no_value=True)
        config.set('DEFAULT', '; template for message')
        config.set('DEFAULT', '; available macros:')
        config.set('DEFAULT', '; message: text from one or multiple posts')
        config.set('DEFAULT', '; source_tags: tags from source config')
        config.set('DEFAULT', '; post_tags: tags parsed from post')
        config.set('DEFAULT', 'layout_template', '{message}<br><br>{source_tags}')
        config.set('DEFAULT', '; template for post item')
        config.set('DEFAULT', '; available macros:')
        config.set('DEFAULT',
                   '; attachments, author, enclosures, id, link, published, summary, tags, title, url')
        config.set('DEFAULT', 'post_template', '<a href="{url}">{title}</a>')

        config.add_section('telegram')
        config.set('telegram', '; telegram bot token')
        config.set('telegram', 'token', '')

        config.add_section('example source')
        config.set('example source', '; source url')
        config.set('example source', '; url = https://example.com/feed.rss')
        config.set('example source', 'url', '')
        config.set('example source', '; parser class')
        config.set('example source', '; available classes:')
        config.set('example source', '; RSSFeedParser')  # TODO fill this automatically
        config.set('example source', 'parser_class', 'RSSFeedParser')
        config.set('example source', '; sender class')
        config.set('example source', '; available classes:')
        config.set('example source', '; TelegramSender')  # TODO fill this automatically
        config.set('example source', 'sender_class', 'TelegramSender')
        config.set('example source', '; source tags')
        config.set('example source', '; you can use this tags in layout_template')
        config.set('example source', '; tags = example_tag1 example_tag2')
        config.set('example source', 'tags', '')
        config.set('example source',
                   '; add parsed tags to source tags')  # NOTE are we need this? we can manage it by post_tags macros
        config.set('example source', 'add_parsed_tags', 'no')
        config.set('example source',
                   '; disable link previews for receivers that support this  (telegram for example)')
        config.set('example source', 'disable_link_preview', 'yes')
        config.set('example source', '; list of receivers where to send messages')
        config.set('example source', '; this can be list of telegram chat id, list of email, etc.')
        config.set('example source', '; receivers = -1001234567890 -1001234567891')
        config.set('example source', 'receivers', '')
        with open(cls.configfile_path, 'w') as configfile:
            config.write(configfile)


field = namedtuple('field', 'name converter_name fallback', defaults=[None, None])


class SourceSettings:
    fields = [
        field('add_parsed_tags', 'getboolean', False),
        field('disable_link_preview', 'getboolean', False),
        field('post_template', 'gettemplate'),
        field('layout_template', 'gettemplate'),
        field('parser_class'),
        field('receivers', 'getlist', []),
        field('sender_class'),
        field('tags', 'getlist', []),
        field('url'),
    ]

    def __init__(self, name, data):
        self.name = name
        data = self.validate(data)
        for field in self.fields:
            setattr(self, field.name, data[field.name])

    def get_send_kwargs(self):
        return {
            'disable_link_preview': self.disable_link_preview
        }

    def validate(self, data):
        attrs = {}
        for field_name, converter_name, fallback in self.fields:
            if converter_name is None:
                value = data.get(field_name)
            else:
                converter = getattr(data, converter_name)
                value = converter(field_name, fallback=fallback)

            validate_method = getattr(self, f'validate_{field_name}', None)
            if validate_method:
                value = validate_method(value)
            attrs[field_name] = value

        return attrs

    def validate_url(self, val):
        if not val:
            raise ImproperlyConfigured(f'You must specify url for "{self.name}" section')

        parse_result = urlparse(val)
        if parse_result.scheme not in ['http', 'https'] or not parse_result.netloc:
            raise ImproperlyConfigured(f'"{val}" is not an URL')

        return val

    def validate_parser_class(self, val):
        try:
            parser_class = load_class(f'feed_proxy.parsers.{val}')
        except AttributeError:
            raise ImproperlyConfigured(f'Wrong parser for "{self.name}" section')

        self.parser = parser_class(self)
        return parser_class

    def validate_sender_class(self, val):
        try:
            sender_class = load_class(f'feed_proxy.senders.{val}')
        except AttributeError:
            raise ImproperlyConfigured(f'Wrong sender for "{self.name}" section')

        return sender_class

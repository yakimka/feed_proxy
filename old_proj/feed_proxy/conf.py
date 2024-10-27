import configparser
import os

from feed_proxy.schema import Source

__all__ = ['settings']

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigReader:
    @classmethod
    def read_from_file(cls, file_path) -> configparser.ConfigParser:
        parser = cls.create_parser()
        parser.read(file_path)
        return parser

    @classmethod
    def create_parser(cls) -> configparser.ConfigParser:
        return configparser.ConfigParser(**cls.get_parser_kwargs())

    @classmethod
    def get_parser_kwargs(cls) -> dict:
        kwargs = {}
        if converters := cls.get_converters():
            kwargs['converters'] = converters
        return kwargs

    @classmethod
    def get_converters(cls) -> dict:
        converters = {}
        for attr in vars(cls):
            if attr.startswith('convert_'):
                name = attr[8:]
                converters[name] = getattr(cls, attr)
        return converters

    @staticmethod
    def convert_tuple(val: str) -> tuple:
        return tuple(filter(None, val.split(' ')))

    @staticmethod
    def convert_template(val: str) -> str:
        return val.replace('<br>', '\n')

    @staticmethod
    def convert_excludepostbytags(val: str) -> tuple:
        return tuple(item.lower() for item in val.split(','))


def get_sources(path: str) -> tuple:
    config = ConfigReader.read_from_file(path)
    return tuple(Source.from_config(config[section]) for section in config.sections())


class Settings:
    _configured = False

    BASE_DIR: str = BASE_DIR
    ENV_PREFIX: str = 'FEED_PROXY_'
    SOURCES: tuple = tuple()
    NUM_MESSAGES_TO_STORE: int = 5
    TELEGRAM_BOT_TOKEN: str = os.getenv(f'{ENV_PREFIX}TELEGRAM_BOT_TOKEN')

    def __setattr__(self, key, value):
        raise RuntimeError("You can't change settings in runtime")

    def configure(self, sources_path: str, **kwargs):
        if self._configured:
            raise RuntimeError('Settings already configured.')

        object.__setattr__(self, 'SOURCES', get_sources(sources_path))
        object.__setattr__(self, '_configured', True)
        for key, value in kwargs.items():
            object.__setattr__(self, key, value)


settings: Settings = Settings()

import importlib
import os
import re
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, List, Union

from alembic.config import Config

PROJECT_PATH = Path(__file__).parent.resolve()

sqltite_db_name = 'feed_proxy.db'
DEFAULT_DB_URL = f'sqlite:///./{sqltite_db_name}'


def load_obj(full_obj_string: str):
    """
    Dynamically load a class from a string
    """

    class_data = full_obj_string.split('.')
    module_path = '.'.join(class_data[:-1])
    class_str = class_data[-1]

    module = importlib.import_module(module_path)
    return getattr(module, class_str)


def make_alembic_config(cmd_opts: Union[Namespace, SimpleNamespace],
                        base_path: str = PROJECT_PATH) -> Config:
    if not os.path.isabs(cmd_opts.config):
        cmd_opts.config = os.path.join(base_path, cmd_opts.config)

    config = Config(file_=cmd_opts.config, ini_section=cmd_opts.name,
                    cmd_opts=cmd_opts)

    alembic_location = config.get_main_option('script_location')
    if not os.path.isabs(alembic_location):
        config.set_main_option('script_location',
                               os.path.join(base_path, alembic_location))
    if cmd_opts.db_url:
        config.set_main_option('sqlalchemy.url', cmd_opts.db_url)

    return config


only_letters_and_underscore = re.compile(r'[^a-zA-Zа-яА-Я0-9_ёЁіІїЇґҐєЄ]')
multiple_underscores = re.compile(r'_+')


def make_hash_tags(tags: Iterable[str]) -> List[str]:
    hash_tags = []
    for tag in tags:
        hash_tag = re.sub(only_letters_and_underscore, '_', tag)
        hash_tag = re.sub(multiple_underscores, '_', hash_tag)
        hash_tags.append(f'#{hash_tag.lower()}')
    return hash_tags


def validate_file(parser, value):
    value = os.path.abspath(value)
    if not os.path.exists(value):
        parser.error(f"The file '{value}' does not exist!")
    return value

import dataclasses
import mimetypes
import os
from datetime import datetime
from functools import cached_property
from typing import Optional, Tuple
from urllib.parse import urlparse

from feed_proxy.utils import make_hash_tags

MISSING = object()
TYPES_MAPPING = {
    bool: 'getboolean',
    float: 'getfloat',
    int: 'getint',
    tuple: 'gettuple',
}
OPTIONS_MAPPING = {
    'post_template': 'gettemplate',
    'parser_class': 'getparser',
    'sender_class': 'getsender',
}


@dataclasses.dataclass(frozen=True)
class Source:
    name: str
    url: str
    receiver: str
    post_template: str
    disable_link_preview: bool = False
    encoding: Optional[str] = None
    tags: tuple = tuple()

    @cached_property
    def hash_tags(self) -> tuple:
        return tuple(make_hash_tags(self.tags))

    @classmethod
    def from_config(cls, config):
        fields = [(f.name, f.type) for f in dataclasses.fields(cls) if f.init and f.name != 'name']
        values = {'name': config.name}

        for name, type_ in fields:
            converter = OPTIONS_MAPPING.get(name) or TYPES_MAPPING.get(type_) or 'get'
            value = getattr(config, converter)(name, MISSING)
            if value is not MISSING:
                values[name] = value
        return cls(**values)


@dataclasses.dataclass(frozen=True)
class Author:
    name: str
    href: str = ''
    email: str = ''


@dataclasses.dataclass(frozen=True)
class Attachment:
    href: str
    type: str
    length: int

    @cached_property
    def is_audio(self) -> bool:
        return self.type.startswith('audio/')

    def guess_extension(self) -> Optional[str]:
        if from_mime := mimetypes.guess_extension(self.type):
            return from_mime

        path = urlparse(self.href).path
        return os.path.splitext(path)[1] or None


@dataclasses.dataclass(frozen=True)
class Post:
    author: str
    authors: Tuple[Author, ...]
    id: str
    url: str
    summary: str
    title: str
    source: Source

    tags: Tuple[str, ...] = tuple()
    attachments: Tuple[Attachment, ...] = tuple()
    published: Optional[datetime] = None

    def has_audio(self) -> bool:
        return any(item.is_audio for item in self.attachments)

    @cached_property
    def audio(self) -> Optional[Attachment]:
        return next((item for item in self.attachments if item.is_audio), None)

    @cached_property
    def hash_tags(self) -> tuple:
        return tuple(make_hash_tags(self.tags))

    @cached_property
    def message_text(self) -> str:
        source_tags = ' '.join(self.source.hash_tags)
        post_tags = ' '.join(self.hash_tags)
        published = ''
        if self.published:
            published = self.published.strftime('%d-%m-%Y %H:%M:%S')

        return self.source.post_template.format(
            all_tags=f'{source_tags} {post_tags}',
            source_tags=source_tags,
            post_tags=post_tags,
            source_name=self.source.name,
            author=self.author,
            url=self.url,
            summary=self.summary,
            title=self.title,
            published=published,
        )

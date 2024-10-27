from datetime import datetime
from typing import Type

from feed_proxy.schema import Attachment, Author, Post, Source


class CycleFactory:
    def __init__(self, factory: Type['Factory'], count: int):
        self.factory = factory
        self.count = count

    def __getattr__(self, name):
        if hasattr(self.factory, name):
            return lambda *args, **kwargs: [
                getattr(self.factory, name)(*args, **kwargs) for _ in range(0, self.count)
            ]


class Factory:
    @classmethod
    def cycle(cls, count):
        """
        Run given method X times:
            Factory.cycle(5).orderItem()  # gives 5 orders
        """
        return CycleFactory(cls, count)

    @classmethod
    def source(cls, **values) -> Source:
        defaults = {
            'name': 'feed_proxy releases',
            'url': 'http://localhost:45432/feed.xml',
            'receiver': '-1001234567890',
            'post_template': '<a href="{url}">{title}</a>\n\n{source_tags}\n{post_tags}',
            'disable_link_preview': True,
            'tags': ('hash', 'tag'),
            'exclude_post_by_tags': tuple(),
        }

        return Source(**{**defaults, **values})

    @classmethod
    def attachment(cls, **values) -> Attachment:
        defaults = {
            'href': 'http://localhost:45432/song.mp3',
            'type': 'audio/mpeg',
            'length': 21652106,
        }
        return Attachment(**{**defaults, **values})

    @classmethod
    def audio_attachment(cls, name='song.mp3', type='audio/mpeg', length=21652106) -> Attachment:
        return cls.attachment(
            href=f'http://localhost:45432/{name}',
            type=type,
            length=length
        )

    @classmethod
    def zip_attachment(cls, name='archive.zip', length=51652106) -> Attachment:
        return cls.attachment(
            href=f'http://localhost:45432/{name}',
            type='application/zip',
            length=length
        )

    @classmethod
    def post(cls, **values) -> Post:
        defaults = {
            'author': 'yakimka',
            'authors': (Author(name='yakimka'),),
            'source': cls.source(),
            'id': 'audio_gt_20mb',
            'url': 'https://github.com/yakimka/feed_proxy/releases/tag/95',
            'summary': 'Lorem ipsum dolor sit amet, consectetur adipisicing.',
            'title': 'feed_proxy 95 release',
            'tags': ('post_hash', 'post_tag'),
            'attachments': (
                cls.audio_attachment(),
                cls.zip_attachment()
            ),
            'published': datetime(2020, 10, 21, 19, 54, 4)
        }

        return Post(**{**defaults, **values})

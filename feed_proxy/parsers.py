import os
import tempfile

import feedparser
import requests
from requests import ConnectionError

from feed_proxy.exceptions import FeedProxyException
from feed_proxy.utils import class_logger


class RSSFeedParser:
    def __init__(self, source):
        self.logger = class_logger(__name__, self.__class__.__name__)

        self.source = source
        self.posts = []

    def parse(self):
        feed = feedparser.parse(self.source.url)
        self.logger.info(f'{self.source.name}: parsed {len(feed.entries)} posts')
        self.posts = [Post(entry) for entry in feed.entries]


class Post:
    fields = [
        'attachments',
        'author',
        'enclosures',
        'id',
        'link',
        'published',
        'summary',
        'tags',
        'title',
        'url'
    ]

    def __init__(self, raw_post):
        self._set_fields(raw_post)

    def _set_fields(self, raw_post):
        for field in self.fields:
            method = getattr(self, f'_parse_{field}', None)
            value = method(raw_post) if method else raw_post[field]
            setattr(self, field, value)

    def to_dict(self):
        return {field: getattr(self, field) for field in self.fields}

    def _parse_tags(self, raw_post):
        tags = []
        for tag in getattr(raw_post, 'tags', []):
            tags.append(tag['term'].lower().replace(' ', '_'))

        return tags

    def _parse_attachments(self, raw_post):
        return [Attachment(item, self) for item in raw_post['enclosures']]

    @classmethod
    def _parse_url(cls, raw_post):
        return raw_post['link']


class Attachment:
    def __init__(self, enclosure, post):
        self.logger = class_logger(__name__, self.__class__.__name__)

        self.post = post
        self.url = enclosure['url']
        self.type = enclosure['type']
        self.file = None

    def __eq__(self, other):
        if isinstance(other, Attachment):
            return self.url == other.url
        return NotImplemented

    @property
    def author(self):
        return self.post.author

    @property
    def title(self):
        return self.post.title

    def get_file_info(self):
        try:
            size, direct_url, file_type = self._get_info_from_head_request()
            return size, direct_url, file_type
        except ConnectionError:
            msg = f'Could not retrieve data from {self.url}'
            self.logger.error(msg)
            raise FeedProxyException(msg)

    def _get_info_from_head_request(self):
        res = requests.head(self.url, allow_redirects=True)
        if not res.ok:
            msg = f'Could not retrieve data from {self.url}'
            self.logger.error(msg)
            raise FeedProxyException(msg)

        size_in_mb = int(res.headers['content-length']) / 1024 / 1024
        return size_in_mb, res.url, res.headers['content-type']

    def download(self):
        try:
            self.logger.info(f'Start download a file for a "{self.post.title}"')
            self.file = self._download_file()
            self.logger.info(f'File for a "{self.post.title}" downloaded')
        except ConnectionError:
            msg = f'Could not download file from {self.url}'
            self.logger.error(msg)
            raise FeedProxyException(msg)

    def _download_file(self):
        res = requests.get(self.url, allow_redirects=True)
        with tempfile.NamedTemporaryFile(delete=False) as file:
            file.write(res.content)
            return file

    def delete(self):
        os.remove(self.file.name)
        self.file = None
        self.logger.warning(f'File for a "{self.post.title}" removed')

    def is_audio(self):
        return self.type.startswith('audio')

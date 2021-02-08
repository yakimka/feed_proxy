import json
import logging
from datetime import datetime
from html.parser import HTMLParser
from typing import List

import feedparser

from feed_proxy.fetchers import fetched_item
from feed_proxy.schema import Attachment, Author, Post, Source

logger = logging.getLogger(__name__)


def parse_posts(fetched: List[fetched_item]) -> List[Post]:
    parsed = []
    for source, status, text in fetched:
        if not status or status >= 400:
            msg = (f"Status code {status} when trying"
                   f" to fetch '{source.url}' from '{source.name}'. Text:\n{text}")
            logger.warning(msg)
            continue
        posts = source.parse(text)
        if not posts:
            msg = f"Can't find posts in '{source.url}' from '{source.name}'. Text:\n{text}"
            logger.warning(msg)
        parsed.extend(posts)
    return parsed


def rss_feed_posts_parser(source: Source, text: str) -> List[Post]:  # noqa C901
    posts = []

    if not text:
        return posts

    def get_published(entry):
        parsed_time = None
        if entry.get('published_parsed'):
            parsed_time = entry.get('published_parsed')
        elif entry.get('updated_parsed'):
            parsed_time = entry.get('updated_parsed')
        if not parsed_time:
            logger.warning(f"Can't parse published date: '{source.name}'; '{entry.title}'")
            return None

        return datetime(*parsed_time[:6])

    def get_author(entry):
        return entry.get('author') or source.name

    def get_authors(entry):
        raw_authors = list(filter(None, entry.get('authors', [])))
        raw_authors = raw_authors or [{'name': get_author(entry)}]

        return tuple(Author(**data) for data in raw_authors)

    def get_tags(entry):
        return tuple(tag.term for tag in entry.get('tags', []))

    def get_attachments(entry):
        return tuple(
            Attachment(length=int(data.pop('length') or 0), **data) for data in entry.enclosures
        )

    feed = feedparser.parse(text, response_headers={'content-type': 'text/html; charset=utf-8'})
    for entry in feed['entries']:
        try:
            id_field = source.id_field
            url = entry[source.url_field]
            posts.append(Post(
                source=source,
                author=get_author(entry),
                authors=get_authors(entry),
                id=entry.get(id_field, url),
                url=url,
                summary=entry.summary,
                title=entry.title,
                attachments=get_attachments(entry),
                published=get_published(entry),
                tags=get_tags(entry),
            ))
        except Exception:
            entry_ = json.dumps(entry, sort_keys=True, indent=4)
            raise ValueError(f"Can't process entry. Source: '{source.name}'\nEntry: {entry_}")

    return posts


class GithubSearchParser(HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.results = []

    def handle_starttag(self, tag, attrs):
        attrs_mapping = dict(attrs)
        if 'data-hydro-click' in attrs_mapping:
            meta = json.loads(attrs_mapping['data-hydro-click'])
            try:
                is_repo = meta['payload']['result']['model_name'] == 'Repository'
            except KeyError:
                is_repo = False

            if is_repo:
                self.extract_data(meta['payload']['result'])

    def extract_data(self, data):
        url: str = data['url']
        title = url.replace('https://github.com/', '')
        author, repo_name = title.split('/', maxsplit=1)

        self.results.append({
            'author': author,
            'authors': (Author(author),),
            'id': url,
            'url': url,
            'summary': '',
            'title': title,
        })


def github_search_parser(source: Source, text: str) -> List[Post]:
    parser = GithubSearchParser()
    parser.feed(text)

    return [Post(source=source, **item) for item in parser.results]

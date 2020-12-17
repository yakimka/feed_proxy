from __future__ import annotations

from collections import namedtuple
from concurrent import futures

import requests

from feed_proxy.conf import settings
from feed_proxy.schema import Source

MAX_WORKERS = 20


def fetch_sources():
    workers = min(MAX_WORKERS, len(settings.SOURCES))
    with futures.ThreadPoolExecutor(workers) as executor:
        res = executor.map(fetch_text_for_source, settings.SOURCES)
    return list(res)


fetched_item = namedtuple('fetched_item', 'source,status_code,text')


# TODO retry on errors
def fetch_text_for_source(source: Source) -> fetched_item:
    res = requests.get(source.url)
    if source.encoding:
        res.encoding = source.encoding
    return fetched_item(source, res.status_code, res.text)

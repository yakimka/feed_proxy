from __future__ import annotations

import logging
from collections import namedtuple
from concurrent import futures

import requests
from requests import RequestException

from feed_proxy.conf import settings
from feed_proxy.schema import Source

logger = logging.getLogger(__name__)

MAX_WORKERS = 20


def fetch_sources():
    workers = min(MAX_WORKERS, len(settings.SOURCES))
    with futures.ThreadPoolExecutor(workers) as executor:
        res = executor.map(fetch_text_for_source, settings.SOURCES)
    return list(res)


fetched_item = namedtuple('fetched_item', 'source,status_code,text')


# TODO retry on errors
def fetch_text_for_source(source: Source) -> fetched_item:
    try:
        headers = {
            # http://www.useragentstring.com/index.php
            'User-Agent': 'Mozilla/5.0 (X11; Linux ppc64le; rv:75.0) Gecko/20100101 Firefox/75.0'
        }
        res = requests.get(source.url, headers=headers)
    except RequestException:
        logger.exception(f"Can't fetch '{source.url}' from '{source.name}'")
        return fetched_item(source, None, '')
    if source.encoding:
        res.encoding = source.encoding
    return fetched_item(source, res.status_code, res.text)

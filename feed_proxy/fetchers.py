from __future__ import annotations

import asyncio
from collections import namedtuple

import aiohttp

from feed_proxy.conf import settings
from feed_proxy.schema import Source


async def fetch_sources():
    tasks = []
    for source in settings.SOURCES:
        tasks.append(asyncio.create_task(fetch_text_for_source(source)))
    return await asyncio.gather(*tasks)


fetched_item = namedtuple('fetched_item', 'source,status_code,text')


# TODO retry on errors
async def fetch_text_for_source(source: Source) -> fetched_item:
    async with aiohttp.request('GET', source.url) as resp:
        status_code = resp.status
        text = await resp.text(encoding=source.encoding)
    return fetched_item(source, status_code, text)

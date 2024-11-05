import asyncio
import logging
from functools import lru_cache
from typing import Optional

import httpx
from tldextract import tldextract

from feed_proxy.sentry.error_tracking import write_warn_message

logger = logging.getLogger(__name__)

# https://user-agents.net/browsers/firefox
DEFAULT_UA = (
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:96.0) Gecko/20100101 Firefox/96.0"
)


@lru_cache(maxsize=None)
def domain_from_url(url: str):
    _, td, tsu = tldextract.extract(url)
    return f"{td}.{tsu}"


async def fetch_text_from_url(url: str, *, encoding="", retry=0) -> str | None:
    # TODO don't fetch if content is not changed
    async with httpx.AsyncClient(
        follow_redirects=True, verify=False, timeout=30  # noqa: S501
    ) as client:
        while True:
            try:
                res = await client.get(
                    url, headers={"user-agent": DEFAULT_UA}, timeout=30.0
                )
                res.raise_for_status()
            except httpx.HTTPError as e:
                if retry > 0:
                    msg = (
                        f"Failed to fetch {url} with {e} and {retry} retries"
                        " left. Retrying..."
                    )
                    logger.warning(msg)
                    retry -= 1
                    await asyncio.sleep(3.0)
                    continue

                msg = f"Error while fetching {url}: error {type(e).__name__}\n{e}"
                write_warn_message(msg, logger.warning)
                return None

            if encoding:
                res.encoding = encoding

            return res.text

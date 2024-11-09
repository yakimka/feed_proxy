import dataclasses
import logging

from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler
from feed_proxy.logic import fetch_text_from_url

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class FetchTextOptions(HandlerOptions):
    DESCRIPTIONS = {
        "url": ("URL", ""),
        "encoding": ("Page encoding", ""),
    }

    url: str
    encoding: str = ""


# @async_lock(key=lambda options: domain_from_url(options.url))
@register_handler(type=HandlerType.fetchers.value, options=FetchTextOptions)
async def fetch_text(*, options: FetchTextOptions) -> str | None:
    return await fetch_text_from_url(options.url, encoding=options.encoding, retry=2)

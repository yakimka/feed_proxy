import logging
from functools import lru_cache

from tldextract import tldextract

logger = logging.getLogger(__name__)

# https://user-agents.net/browsers/firefox
DEFAULT_UA = (
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:96.0) Gecko/20100101 Firefox/96.0"
)


@lru_cache(maxsize=None)
def domain_from_url(url: str):
    result = tldextract.extract(url)
    return result.fqdn

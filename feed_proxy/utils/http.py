import logging
from functools import lru_cache

from tldextract import tldextract

logger = logging.getLogger(__name__)

# https://www.whatismybrowser.com/guides/the-latest-user-agent/firefox
DEFAULT_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0"
ACCEPT_HEADER = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


@lru_cache(maxsize=None)
def domain_from_url(url: str) -> str:
    result = tldextract.extract(url)
    return result.fqdn

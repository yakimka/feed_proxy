import asyncio
import dataclasses
import hashlib
import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

from feed_proxy.entities import Post
from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler
from feed_proxy.utils.text import make_hash_tags

logger = logging.getLogger(__name__)

BASE_URL = "https://www.idealista.com"


@dataclasses.dataclass()
class IdealistaItem(Post):
    post_id: str
    title: str
    url: str
    money: str
    details: list[str]
    source_tags: tuple | list

    def __str__(self) -> str:
        return self.title

    def template_kwargs(self) -> dict[str, Any]:
        return {
            "post_id": self.post_id,
            "title": self.title,
            "url": self.url,
            "source_tags": "; ".join(self.source_tags),
            "source_hash_tags": " ".join(make_hash_tags(self.source_tags)),
            "money": self.money,
            "details": "; ".join(self.details),
        }


@register_handler(
    type=HandlerType.parsers,
    return_model=IdealistaItem,
)
async def idealista(
    text: str, *, options: HandlerOptions | None = None  # noqa: U100
) -> list[IdealistaItem]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _parse_idealista, text)


def _parse_idealista(html: str) -> list[IdealistaItem]:
    items: list[IdealistaItem] = []

    if not html:
        return items

    soup = BeautifulSoup(html, "lxml")

    for article in soup.select("article.item"):
        try:
            link_el = article.select_one("a.item-link")
            if not link_el:
                continue

            href = str(link_el.get("href", ""))
            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            title = link_el.get_text(strip=True)

            price_el = article.select_one(".item-price")
            money = price_el.get_text(strip=True) if price_el else ""

            details = _extract_details(article)
            post_id = _make_post_id(_extract_post_id_from_url(url), details)

            items.append(
                IdealistaItem(
                    post_id=post_id,
                    title=title,
                    url=url,
                    money=money,
                    details=details,
                    source_tags=[],
                )
            )
        except Exception:  # noqa: PIE786
            logger.exception("Failed to parse Idealista item: %s", article)

    return items


def _extract_post_id_from_url(url: str) -> str:
    # URL format: https://www.idealista.com/inmueble/12345678/
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else url


def _make_post_id(id_from_url: str, details: list[str]) -> str:
    # use details hash because we want to show updated posts
    details_hash = hashlib.sha256("_".join(details).encode("utf-8")).hexdigest()
    return f"{id_from_url}_{details_hash}"


def _extract_details(article: Tag) -> list[str]:
    details = []

    for detail_el in article.select(".item-detail"):
        text = detail_el.get_text(strip=True)
        if text:
            details.append(text)

    return details

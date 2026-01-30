import asyncio
import dataclasses
import json
import logging
import re
from typing import Any

from feed_proxy.entities import Post
from feed_proxy.handlers import HandlerOptions, HandlerType, register_handler
from feed_proxy.utils.text import make_hash_tags

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fotocasa.es"

BUILDING_TYPES = {
    "Flat": "Piso",
    "House": "Casa",
    "Penthouse": "Ático",
    "Duplex": "Dúplex",
    "Studio": "Estudio",
    "Loft": "Loft",
    "Chalet": "Chalet",
}


@dataclasses.dataclass()
class FotocasaItem(Post):
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
            "details": " ".join(self.details),
        }


@register_handler(
    type=HandlerType.parsers,
    return_model=FotocasaItem,
)
async def fotocasa(
    text: str, *, options: HandlerOptions | None = None  # noqa: U100
) -> list[FotocasaItem]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _parse_fotocasa, text)


def _parse_fotocasa(html: str) -> list[FotocasaItem]:
    items: list[FotocasaItem] = []

    if not html:
        return items

    # Try to parse JSON from __INITIAL_PROPS__
    match = re.search(
        r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\("(.+?)"\)', html, re.DOTALL
    )
    if not match:
        logger.warning("Could not find __INITIAL_PROPS__ in Fotocasa HTML")
        return items

    try:
        json_str = match.group(1)
        json_str = json_str.encode().decode("unicode_escape")
        data = json.loads(json_str)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.exception("Failed to parse Fotocasa JSON: %s", e)
        return items

    real_estates = (
        data.get("initialSearch", {}).get("result", {}).get("realEstates", [])
    )

    for estate in real_estates:
        try:
            estate_id = str(estate.get("id", ""))
            if not estate_id:
                continue

            detail = estate.get("detail", {})
            href = detail.get("es-ES", "") if isinstance(detail, dict) else ""
            if not href:
                continue
            url = f"{BASE_URL}{href}"

            money = estate.get("price", "")
            title = _build_title(estate)
            details = _extract_details_from_features(estate)
            post_id = _make_post_id(estate_id, money)

            items.append(
                FotocasaItem(
                    post_id=post_id,
                    title=title,
                    url=url,
                    money=money,
                    details=details,
                    source_tags=[],
                )
            )
        except Exception:  # noqa: PIE786
            logger.exception("Failed to parse Fotocasa item: %s", estate)

    return items


def _build_title(estate: dict) -> str:
    building_type = estate.get("buildingType", "")
    building_type_es = BUILDING_TYPES.get(building_type, building_type)

    features = estate.get("features", [])
    features_dict = {f["key"]: f["value"] for f in features if "key" in f}
    surface = features_dict.get("surface")

    location = estate.get("location", "")

    parts = [building_type_es]
    if surface:
        parts.append(f"de {surface} m²")
    if location:
        parts.append(f"en {location}")

    return " ".join(parts)


def _extract_details_from_features(estate: dict) -> list[str]:
    details = []

    features = estate.get("features", [])
    features_dict = {f["key"]: f["value"] for f in features if "key" in f}

    rooms = features_dict.get("rooms")
    if rooms:
        details.append(f"{rooms} habs")

    bathrooms = features_dict.get("bathrooms")
    if bathrooms:
        details.append(f"{bathrooms} baño" if bathrooms == 1 else f"{bathrooms} baños")

    surface = features_dict.get("surface")
    if surface:
        details.append(f"{surface} m²")

    if features_dict.get("elevator"):
        details.append("Ascensor")
    if features_dict.get("heating"):
        details.append("Calefacción")
    if features_dict.get("furnished"):
        details.append("Amueblado")

    return details


def _make_post_id(estate_id: str, money: str) -> str:
    # use money hash because we want to show updated posts
    return f"{estate_id}_{money}"

import re
import string
from collections.abc import Iterable

only_letters_and_underscore = re.compile(r"[^a-zA-Zа-яА-Я0-9_ёЁіІїЇґҐєЄ]")
multiple_underscores = re.compile(r"_+")


def make_hash_tags(tags: Iterable[str]) -> list[str]:
    hash_tags = []
    for tag in tags:
        hash_tag = re.sub(only_letters_and_underscore, "_", tag)
        hash_tag = re.sub(multiple_underscores, "_", hash_tag)
        hash_tags.append(f"#{hash_tag.lower()}")
    return hash_tags


def template_to_text(template_string: str, **kwargs) -> str:
    template = string.Template(template_string)
    return template.safe_substitute(kwargs)

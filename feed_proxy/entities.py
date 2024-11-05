from dataclasses import dataclass
from typing import Protocol

from dacite import from_dict


@dataclass
class Post(Protocol):
    post_id: str
    source_tags: tuple | list

    def template_kwargs(self) -> dict:
        raise NotImplementedError

    @classmethod
    def fields_schema(cls) -> dict:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict):
        return from_dict(cls, data=data)

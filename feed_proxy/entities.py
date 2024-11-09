from dataclasses import dataclass, field
from typing import Any, Protocol

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


@dataclass
class Message:
    post_id: str
    template: str
    template_kwargs: dict = field(default_factory=dict)


@dataclass
class Receiver:
    id: str
    type: str
    options: dict[str, Any]


@dataclass
class Modifier:
    type: str
    options: dict[str, Any]


@dataclass
class Stream:
    receiver: Receiver
    receiver_options: dict[str, Any]
    intervals: list[str]
    squash: bool
    message_template: str | None
    message_template_id: str | None
    modifiers: list[Modifier]
    active: bool


@dataclass
class Source:
    id: str
    fetcher_type: str
    fetcher_options: dict[str, Any]
    parser_type: str
    parser_options: dict[str, Any]
    tags: list[str]
    streams: list[Stream]

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from dacite import from_dict


@dataclass
class Post(Protocol):
    post_id: str
    source_tags: tuple | list

    def __str__(self) -> str:
        raise NotImplementedError

    def template_kwargs(self) -> dict:
        raise NotImplementedError

    @classmethod
    def fields_schema(cls) -> dict:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict) -> Post:
        return from_dict(cls, data=data)


@dataclass(kw_only=True)
class Message:
    post_id: str
    template: str
    template_kwargs: dict = field(default_factory=dict)


@dataclass(kw_only=True)
class Modifier:
    type: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Stream:
    receiver_type: str
    receiver_options: dict[str, Any] = field(default_factory=dict)
    intervals: list[str] = field(default_factory=list)
    squash: bool = True
    message_template: str | None = None
    message_template_id: str | None = None
    modifiers: list[Modifier] = field(default_factory=list)
    active: bool = True

    def __post_init__(self) -> None:
        if self.message_template and self.message_template_id:
            raise ValueError(
                "Only one of message_template or message_template_id can be set"
            )
        if not self.message_template and not self.message_template_id:
            raise ValueError(
                "One of message_template or message_template_id must be set"
            )


@dataclass(kw_only=True)
class Source:
    id: str
    fetcher_type: str
    fetcher_options: dict[str, Any] = field(default_factory=dict)
    parser_type: str
    parser_options: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    streams: list[Stream]

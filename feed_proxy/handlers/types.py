from typing import Protocol


class Message(Protocol):
    text: str
    template: str
    template_kwargs: dict

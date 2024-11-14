from typing import Any, Protocol


class Message(Protocol):
    text: str
    template: str
    template_kwargs: dict[str, Any]

from collections.abc import Callable
from functools import partial

from sentry_sdk import capture_message

DEFAULT_WRITERS: tuple[Callable[[str], None]] = (  # type: ignore [assignment]
    partial(capture_message, level="warning"),
)


def write_warn_message(message: str, *writer: Callable[[str], None]) -> None:
    writers = [*DEFAULT_WRITERS, *writer]
    for writer_ in writers:
        writer_(message)

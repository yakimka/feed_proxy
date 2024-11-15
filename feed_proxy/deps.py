import os
from collections.abc import Callable
from functools import partial
from typing import Any

import yaml

from feed_proxy.storage import (
    MemoryMessagesOutbox,
    MemoryPostStorage,
    MessagesOutbox,
    PostStorage,
)


def _yaml_string_constructor(self: Any, node: Any) -> Any:
    value = self.construct_yaml_str(node)
    if value.startswith("ENV:"):
        return os.environ[f"{value[4:]}"].strip()
    return value


yaml.Loader.add_constructor("tag:yaml.org,2002:str", _yaml_string_constructor)
yaml.SafeLoader.add_constructor("tag:yaml.org,2002:str", _yaml_string_constructor)


def get_yaml_loader() -> Callable[[str], dict]:
    return yaml.safe_load


def get_yaml_dumper() -> Callable[[dict], str]:
    return partial(  # type: ignore[return-value]
        yaml.safe_dump,
        default_flow_style=False,
    )


def get_post_storage() -> PostStorage:
    return MemoryPostStorage()


def get_outbox_queue() -> MessagesOutbox:
    return MemoryMessagesOutbox()

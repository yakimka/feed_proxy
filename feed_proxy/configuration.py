from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING, Any

import yaml
from dacite import exceptions, from_dict

from feed_proxy.entities import Receiver, Source
from feed_proxy.handlers import init_handlers_config

if TYPE_CHECKING:
    from pathlib import Path


def _yaml_string_constructor(self: Any, node: Any, env_prefix: Any) -> Any:
    value = self.construct_yaml_str(node)
    if value.startswith("ENV:"):
        return os.environ[f"{env_prefix}{value[4:]}"].strip()
    return value


string_constructor = partial(_yaml_string_constructor, env_prefix="")
yaml.Loader.add_constructor("tag:yaml.org,2002:str", string_constructor)
yaml.SafeLoader.add_constructor("tag:yaml.org,2002:str", string_constructor)


@dataclass
class MessageTemplate:
    id: str
    template: str


class LoadConfigurationError(Exception):
    pass


def load_configuration(path: Path) -> list[Source]:  # noqa: C901
    configurations: dict[str, dict] = {}
    for file in chain(path.glob("*.yaml"), path.glob("*.yml")):
        conf_parts = yaml.safe_load(file.read_text())
        configurations |= json.loads(json.dumps(conf_parts))

    try:
        init_handlers_config(configurations.get("handlers", {}))

        receivers = {}
        for receiver_id, receiver in configurations.get("receivers", {}).items():
            receiver["id"] = receiver_id
            receivers[receiver_id] = from_dict(Receiver, receiver)

        message_templates = {}
        for msg_tmpl_id, msg_tmpl in configurations.get(
            "message-templates", {}
        ).items():
            msg_tmpl["id"] = msg_tmpl_id
            message_templates[msg_tmpl_id] = from_dict(MessageTemplate, msg_tmpl)

        sources = []
        for source_id, source in configurations.get("sources", {}).items():
            source_streams = source.pop("streams", {})
            for receiver_id, stream in source_streams.items():
                stream["receiver"] = receivers.get(receiver_id)
                if stream.get("message_template_id") and stream.get("message_template"):
                    raise LoadConfigurationError(
                        "Only one of message_template_id or "
                        f"message_template can be set: {source_id}"
                    )
                if message_template_id := stream.get("message_template_id"):
                    message_template = message_templates.get(message_template_id)
                    if not message_template:
                        raise LoadConfigurationError(
                            f"Message template {message_template_id} "
                            f"not found: {source_id}"
                        )
                    stream["message_template"] = message_template.template

            source["id"] = source_id
            source["streams"] = list(source_streams.values())
            sources.append(from_dict(Source, source))
    except (exceptions.DaciteError, LoadConfigurationError) as e:
        print(e)
        raise SystemExit(1)

    if not configurations:
        raise LoadConfigurationError("No configuration files found")

    return sources

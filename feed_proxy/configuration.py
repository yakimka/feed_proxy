from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING, Any

import yaml
from dacite import Config, exceptions, from_dict

from feed_proxy.entities import Source
from feed_proxy.handlers import HandlerType, InitHandlersError, init_registered_handlers

if TYPE_CHECKING:
    from pathlib import Path


def _yaml_string_constructor(self: Any, node: Any, env_prefix: Any) -> Any:
    value = self.construct_yaml_str(node)
    if value.startswith("ENV:"):
        return os.environ[f"{env_prefix}{value[4:]}"].strip()
    return value


def get_yaml_reader(env_prefix: str = "") -> Callable[[str], dict]:
    string_constructor = partial(_yaml_string_constructor, env_prefix=env_prefix)
    yaml.Loader.add_constructor("tag:yaml.org,2002:str", string_constructor)
    yaml.SafeLoader.add_constructor("tag:yaml.org,2002:str", string_constructor)
    return yaml.safe_load


def read_configuration_files(
    path: Path, reader: Callable[[str], dict]
) -> dict[str, Any]:
    configurations: dict[str, dict] = {}
    for file in chain(path.glob("*.yaml"), path.glob("*.yml")):
        conf_parts = reader(file.read_text()) or {}
        configurations |= json.loads(json.dumps(conf_parts))
    return configurations


class LoadConfigurationError(Exception):
    pass


def load_sources(configurations: dict[str, Any]) -> list[Source]:
    try:
        result = load_configuration(configurations)
        return result.sources
    except (LoadConfigurationError, InitHandlersError) as e:
        print(e)
        raise SystemExit(1) from None


def load_configuration(configurations: dict[str, Any]) -> Configuration:
    if not configurations:
        raise LoadConfigurationError("No configuration files found")

    result = read_configuration(configurations)
    init_registered_handlers(result)
    return result


@dataclass
class SubHandlerConfig:
    handler_type: HandlerType
    name: str
    type: str
    init_options: dict[str, Any]


@dataclass
class Configuration:
    sources: list[Source]
    subhandlers: list[SubHandlerConfig]


def read_configuration(config: dict[str, Any]) -> Configuration:
    sources = _parse_sources(config)
    if not sources:
        raise LoadConfigurationError(
            "Configuration must contain filled 'sources' block"
        )

    subhandlers = _parse_subhandlers(config)

    return Configuration(sources=sources, subhandlers=subhandlers)


def _parse_subhandlers(config: dict) -> list[SubHandlerConfig]:
    result = []
    for handler_type, subhandlers in config.get("handlers", {}).items():
        for handler_name, subconfig in subhandlers.items():
            try:
                result.append(
                    from_dict(
                        SubHandlerConfig,
                        {
                            "handler_type": handler_type,
                            "name": handler_name,
                            "type": subconfig.get("type"),
                            "init_options": subconfig.get("init_options"),
                        },
                        config=Config(cast=[Enum]),
                    )
                )
            except exceptions.DaciteError as e:
                raise LoadConfigurationError(f"Handler {handler_name}: {e}") from None
    return result


def _parse_sources(config: dict) -> list[Source]:
    sources = []
    for source_id, source in config.get("sources", {}).items():
        source["id"] = source_id
        try:
            sources.append(from_dict(Source, source))
        except exceptions.DaciteError as e:
            raise LoadConfigurationError(f"Source {source_id}: {e}") from None
    return sources

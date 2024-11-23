from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from itertools import chain
from typing import TYPE_CHECKING, Any, Literal

from dacite import Config, exceptions, from_dict
from picodi import Provide, inject, registry

from feed_proxy.deps import get_app_settings, get_yaml_loader
from feed_proxy.entities import Source
from feed_proxy.handlers import HandlerType, InitHandlersError, init_registered_handlers

if TYPE_CHECKING:
    from pathlib import Path


class LoadConfigurationError(Exception):
    pass


@lru_cache(maxsize=1)
@inject
def read_configuration_from_folder(
    folder_path: Path, yaml_loader: Callable[[str], dict] = Provide(get_yaml_loader)
) -> Configuration:
    configurations = read_configuration_files(folder_path, yaml_loader)
    try:
        conf = load_configuration(configurations)
        registry.override(get_app_settings, lambda: conf.app_settings)
        return conf
    except (LoadConfigurationError, InitHandlersError) as e:
        print(e)
        raise SystemExit(1) from None


def load_configuration(configurations: dict[str, Any]) -> Configuration:
    if not configurations:
        raise LoadConfigurationError("No configuration files found")

    result = read_configuration(configurations)
    init_registered_handlers(result)
    return result


def read_configuration_files(
    path: Path, yaml_loader: Callable[[str], dict]
) -> dict[str, Any]:
    configurations: dict[str, dict] = {}
    for file in chain(path.glob("*.yaml"), path.glob("*.yml")):
        conf_parts = yaml_loader(file.read_text()) or {}
        configurations |= json.loads(json.dumps(conf_parts))
    return configurations


@dataclass
class SubHandlerConfig:
    handler_type: HandlerType
    name: str
    type: str
    init_options: dict[str, Any]


@dataclass
class AppSettings:
    log_level: str = "INFO"
    sentry_dsn: str | None = None
    post_storage: Literal["memory", "sqlite"] = "memory"
    outbox_storage: Literal["memory", "sqlite"] = "memory"
    sqlite_db: str | None = None


@dataclass
class Configuration:
    app_settings: AppSettings
    sources: list[Source]
    subhandlers: list[SubHandlerConfig]
    raw: dict[str, Any]


def read_configuration(config: dict[str, Any]) -> Configuration:
    sources = _parse_sources(config)
    if not sources:
        raise LoadConfigurationError(
            "Configuration must contain filled 'sources' block"
        )

    subhandlers = _parse_subhandlers(config)
    settings = _parse_app_settings(config)
    raw_config = {
        "handlers": config.get("handlers", {}),
        "sources": config.get("sources", {}),
        "settings": config.get("settings", {}),
    }

    return Configuration(
        app_settings=settings,
        sources=sources,
        subhandlers=subhandlers,
        raw=raw_config,
    )


def _parse_app_settings(config: dict) -> AppSettings:
    try:
        return from_dict(AppSettings, config.get("settings", {}))
    except exceptions.DaciteError as e:
        raise LoadConfigurationError(f"App settings: {e}") from None


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

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable, Generator
from functools import partial
from typing import TYPE_CHECKING, Any

import yaml
from picodi import Provide, SingletonScope, dependency, inject
from picodi.helpers import enter

from feed_proxy.messages_outbox import MessagesOutbox
from feed_proxy.observability import Metrics, NullMetrics, PrometheusMetrics
from feed_proxy.storage import (
    MemoryMessagesOutboxStorage,
    MemoryPostStorage,
    MessagesOutboxStorage,
    PostStorage,
    SqliteMessagesOutboxStorage,
    SqlitePostStorage,
    create_sqlite_conn,
)

if TYPE_CHECKING:
    from feed_proxy.configuration import AppSettings


def get_app_settings() -> AppSettings:
    raise NotImplementedError("get_app_settings need to be overridden")


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


@dependency(scope_class=SingletonScope)
@inject
def get_sqlite_conn(
    settings: AppSettings = Provide(get_app_settings),
) -> sqlite3.Connection:
    assert settings.sqlite_db is not None, "sqlite_db is not set"
    return create_sqlite_conn(str(settings.sqlite_db))


def get_memory_post_storage() -> MemoryPostStorage:
    return MemoryPostStorage()


@inject
def get_sqlite_post_storage(
    conn: sqlite3.Connection = Provide(get_sqlite_conn),
) -> SqlitePostStorage:
    return SqlitePostStorage(conn)


@inject
def get_post_storage(settings: AppSettings = Provide(get_app_settings)) -> PostStorage:
    if settings.post_storage == "sqlite":
        dep: Callable = get_sqlite_post_storage
    elif settings.post_storage == "memory":
        dep = get_memory_post_storage
    else:
        raise ValueError(f"Unknown post storage type: {settings.post_storage}")

    with enter(dep) as post_storage:
        return post_storage


def get_memory_outbox_storage() -> MemoryMessagesOutboxStorage:
    return MemoryMessagesOutboxStorage()


@inject
def get_sqlite_outbox_storage(
    conn: sqlite3.Connection = Provide(get_sqlite_conn),
) -> SqliteMessagesOutboxStorage:
    return SqliteMessagesOutboxStorage(conn)


@inject
def get_outbox_storage(
    settings: AppSettings = Provide(get_app_settings),
) -> MessagesOutboxStorage:
    if settings.outbox_storage == "sqlite":
        dep: Callable = get_sqlite_outbox_storage
    elif settings.outbox_storage == "memory":
        dep = get_memory_outbox_storage
    else:
        raise ValueError(f"Unknown outbox storage type: {settings.outbox_storage}")

    with enter(dep) as outbox_storage:
        return outbox_storage


@inject
def get_outbox_queue(
    storage: MessagesOutboxStorage = Provide(get_outbox_storage),
) -> MessagesOutbox:
    return MessagesOutbox(storage)


@dependency(scope_class=SingletonScope)
@inject
def get_metrics(
    app_settings: AppSettings = Provide(get_app_settings),
) -> Generator[Metrics, None, None]:
    if app_settings.metrics_client == "null":
        metrics: Metrics = NullMetrics()
    elif app_settings.metrics_client == "prometheus":
        metrics = PrometheusMetrics(app_settings.metrics_file)
    else:
        raise ValueError(f"Unknown metrics client: {app_settings.metrics_client}")

    try:
        yield metrics
    finally:
        metrics.stop_daemon()

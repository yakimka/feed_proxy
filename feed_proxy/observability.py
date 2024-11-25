from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import sentry_sdk
from prometheus_client import CollectorRegistry, Counter, Gauge, write_to_textfile
from sentry_sdk.integrations.logging import LoggingIntegration

if TYPE_CHECKING:
    from feed_proxy.configuration import AppSettings


logger = logging.getLogger(__name__)


def setup_logging_instruments(app_settings: AppSettings) -> None:
    log_level = _parse_logging_level_from_string(app_settings.log_level)
    logging.basicConfig(level=log_level)

    if not app_settings.sentry_dsn:
        logger.warning("Sentry DSN is not set")
        return

    sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
    sentry_sdk.init(dsn=app_settings.sentry_dsn, integrations=[sentry_logging])


def _parse_logging_level_from_string(level: str) -> int:
    levels_mapping = logging.getLevelNamesMapping()
    return levels_mapping.get(level.upper(), logging.INFO)


class Metrics(Protocol):
    def increment_sources_fetched(self, source_id: str, status: str) -> None:
        pass

    def increment_posts_parsed(self, source_id: str) -> None:
        pass

    def increment_messages_prepared(
        self, source_id: str, receiver_id: str, messages_count: int
    ) -> None:
        pass

    def increment_messages_sent(
        self, source_id: str, receiver_id: str, messages_count: int
    ) -> None:
        pass

    def write_to_file(self) -> None:
        pass

    def start_daemon(self) -> None:
        pass

    def stop_daemon(self) -> None:
        pass


class NullMetrics:
    def increment_sources_fetched(
        self, source_id: str, status: str  # noqa: U100
    ) -> None:
        return None

    def increment_posts_parsed(self, source_id: str) -> None:  # noqa: U100
        return None

    def increment_messages_prepared(
        self, source_id: str, receiver_id: str, messages_count: int  # noqa: U100
    ) -> None:
        return None

    def increment_messages_sent(
        self, source_id: str, receiver_id: str, messages_count: int  # noqa: U100
    ) -> None:
        return None

    def write_to_file(self) -> None:
        return None

    def start_daemon(self) -> None:
        print("NullMetrics: start_daemon")

    def stop_daemon(self) -> None:
        print("NullMetrics: stop_daemon")


class PrometheusMetrics:
    def __init__(self, textfile_path: Path | str) -> None:
        assert textfile_path, "Textfile path should be provided"
        self._textfile_path = Path(textfile_path).resolve()
        self._daemon_running = False
        self.registry = CollectorRegistry()
        self._sources_fetched = Counter(
            "sources_fetched_total",
            "Number of sources fetched",
            ["app_name", "source_id", "status"],
            registry=self.registry,
        )
        self._posts_parsed = Counter(
            "posts_parsed_total",
            "Number of posts parsed",
            ["app_name", "source_id"],
            registry=self.registry,
        )
        self._messages_prepared = Counter(
            "messages_prepared_total",
            "Number of messages prepared",
            ["app_name", "source_id", "receiver_id"],
            registry=self.registry,
        )
        self._messages_sent = Counter(
            "messages_sent_total",
            "Number of messages sent",
            ["app_name", "source_id", "receiver_id"],
            registry=self.registry,
        )
        self._app_uptime = Gauge(
            "app_uptime_seconds_total",
            "Application uptime in seconds",
            ["app_name"],
            registry=self.registry,
        )
        self._app_start_time = time.monotonic()
        self._app_name = "feed_proxy_worker"

    def increment_sources_fetched(self, source_id: str, status: str) -> None:
        self._sources_fetched.labels(self._app_name, source_id, status).inc()

    def increment_posts_parsed(self, source_id: str) -> None:
        self._posts_parsed.labels(self._app_name, source_id).inc()

    def increment_messages_prepared(
        self, source_id: str, receiver_id: str, messages_count: int
    ) -> None:
        self._messages_prepared.labels(self._app_name, source_id, receiver_id).inc(
            messages_count
        )

    def increment_messages_sent(
        self, source_id: str, receiver_id: str, messages_count: int
    ) -> None:
        self._messages_sent.labels(self._app_name, source_id, receiver_id).inc(
            messages_count
        )

    def write_to_file(self) -> None:
        write_to_textfile(str(self._textfile_path), self.registry)

    def update_uptime(self) -> None:
        self._app_uptime.labels(self._app_name).set(
            time.monotonic() - self._app_start_time
        )

    def start_daemon(self) -> None:
        def write_to_file() -> None:
            self._daemon_running = True
            while self._daemon_running:
                self.update_uptime()
                self.write_to_file()
                time.sleep(10)

        threading.Thread(target=write_to_file, daemon=True).start()

    def stop_daemon(self) -> None:
        self._daemon_running = False

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import sentry_sdk
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

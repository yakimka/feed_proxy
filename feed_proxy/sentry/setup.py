import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)


def setup_logging(dsn: str | None) -> None:
    if not dsn:
        logger.warning("Sentry DSN is not set")
        return

    sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
    sentry_sdk.init(dsn=dsn, integrations=[sentry_logging])

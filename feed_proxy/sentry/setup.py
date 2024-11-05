import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)


def setup_logging(dsn: str | None):
    if not dsn:
        logger.warning("Sentry DSN is not set")
        return

    sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
    sentry_sdk.init(dsn=dsn, integrations=[sentry_logging])


def setup_fastapi(dsn: str | None):
    if not dsn:
        logger.warning("Sentry DSN is not set")
        return

    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0,
    )

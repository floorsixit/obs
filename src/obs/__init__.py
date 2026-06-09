"""Shared observability: structlog logging + Sentry, standardized across services.

A single canonical logging + Sentry setup so each service doesn't hand-roll its own —
fix here, bump the tag, and consumers pin it.

    from obs import configure_logging, init_sentry, get_logger, bind_context

    configure_logging(service="core")
    init_sentry(settings.sentry_dsn, environment=settings.env,
                server_name="core", release=settings.release)
    log = get_logger()
    log.info("request_handled", path="/api/v1/accounts")
"""

from obs.logging import bind_context, configure_logging, get_logger
from obs.sentry import init_sentry

__all__ = ["bind_context", "configure_logging", "get_logger", "init_sentry"]

"""Structured logging via structlog — console (dev) / JSON (prod), stdlib-bridged.

- dev (`ENV` != production): coloured console; prod: JSON to stderr (machine-parseable)
- async-safe context via contextvars (bind once in middleware, flows everywhere)
- intercepts stdlib logging (httpx, uvicorn, sqlalchemy) into the same format
- optionally forwards each event to Sentry Logs (needs `init_sentry`, enable_logs=True)
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Sequence
from typing import Any

import structlog

# Third-party loggers that are noisy at INFO; pinned to WARNING.
_NOISY = ("httpx", "httpcore", "uvicorn.access", "sqlalchemy.engine")


def _sentry_log_processor(_: Any, __: Any, event_dict: dict) -> dict:
    """Forward this event to Sentry's Logs product (no-op unless enable_logs=True)."""
    try:
        import sentry_sdk.logger as sentry_logger
    except ImportError:  # sentry-sdk always present as a dep, but stay defensive
        return event_dict
    level = (event_dict.get("level") or "info").lower()
    emit = getattr(sentry_logger, level, sentry_logger.info)
    # Attribute serialisation can fail on exotic types; don't let logging crash.
    with contextlib.suppress(TypeError, ValueError):
        emit(
            event_dict.get("event", ""),
            **{k: v for k, v in event_dict.items() if k not in ("event", "level", "timestamp")},
        )
    return event_dict


def configure_logging(
    service: str,
    *,
    extra_processors: Sequence[Any] = (),
    forward_to_sentry: bool = True,
) -> None:
    """Configure structlog once at process startup.

    Args:
        service: tag added to every event (use the project/app name; matches the
            Sentry `server_name` and the Docker `<project>` token).
        extra_processors: structlog processors inserted before rendering — the
            per-service extension point (e.g. a redaction or dict-repr filter).
        forward_to_sentry: also emit events to Sentry Logs (pair with `init_sentry`).
    """
    is_prod = os.getenv("ENV", "development").lower() == "production"
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

    def _add_service(_: Any, __: Any, event_dict: dict) -> dict:
        event_dict.setdefault("service", service)
        return event_dict

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_service,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        *extra_processors,
    ]
    if forward_to_sentry:
        shared.append(_sentry_log_processor)

    renderer = structlog.processors.JSONRenderer() if is_prod else structlog.dev.ConsoleRenderer()

    def _drop_internal(_: Any, __: Any, event_dict: dict) -> dict:
        for key in ("_record", "_from_structlog", "_logger", "_name"):
            event_dict.pop(key, None)
        return event_dict

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ExtraAdder(),
            structlog.processors.format_exc_info,
            _drop_internal,
            renderer,
        ],
        foreign_pre_chain=shared,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            *shared,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(**initial_context: Any) -> Any:
    """Get a structlog logger, optionally pre-bound with context."""
    log = structlog.get_logger()
    return log.bind(**initial_context) if initial_context else log


def bind_context(**context: Any) -> None:
    """Bind request/job context (e.g. `request_id`) onto all downstream logs.

    Async-safe via contextvars — call once in middleware; every later `get_logger`
    event in the same context carries it. Clear with
    `structlog.contextvars.clear_contextvars()` at request teardown.
    """
    structlog.contextvars.bind_contextvars(**context)

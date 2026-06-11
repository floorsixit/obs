"""Structured logging via structlog — console (dev) / JSON (prod), stdlib-bridged.

- local/test: coloured console; hosted (dev/prod): JSON to stderr (machine-parseable).
  Environment comes from the `environment=` arg if given, else the `ENV` env var.
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

# ASGI/WSGI server loggers. When run via their CLIs (`uvicorn app:app`, gunicorn),
# these install their own handlers with propagate=False, so their output bypasses our
# root handler and renders in the server's default format — in prod that means
# lifecycle/access lines escape the JSON pipeline. We clear those handlers and
# re-enable propagation so they flow through the root obs handler. This relies on
# configure_logging running *after* the server configures logging, which holds for the
# standard CLI path (the server configures logging, then imports the app — and the app
# is where configure_logging is called).
_SERVER_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "gunicorn",
    "gunicorn.error",
    "gunicorn.access",
)


# Keys that are pipeline internals, not log attributes — never forward them to Sentry.
_NON_ATTR_KEYS = frozenset(
    ("event", "level", "timestamp", "_record", "_from_structlog", "_logger", "_name", "color_message")
)


def _sentry_log_processor(_: Any, __: Any, event_dict: dict) -> dict:
    """Forward this event to Sentry's Logs product (no-op unless enable_logs=True)."""
    # Recursion guard: the Sentry SDK logs its own activity (e.g. "Sending envelope")
    # via stdlib logging, which our bridge feeds back here. Forwarding those into Sentry
    # Logs makes the SDK log again → an exponential feedback loop (catastrophic under
    # debug=True). Never forward records that originate from the SDK's own logger.
    record = event_dict.get("_record")
    if record is not None and getattr(record, "name", "").startswith("sentry_sdk"):
        return event_dict

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
            **{k: v for k, v in event_dict.items() if k not in _NON_ATTR_KEYS},
        )
    return event_dict


def configure_logging(
    service: str,
    *,
    environment: str | None = None,
    extra_processors: Sequence[Any] = (),
    forward_to_sentry: bool = True,
) -> None:
    """Configure structlog once at process startup.

    Args:
        service: tag added to every event (use the project/app name; matches the
            Sentry `server_name` and the Docker `<project>` token).
        environment: the deployment environment (the workspace ``ENV`` vocabulary,
            ``local|dev|prod|test``). Hosted environments (``dev``, ``prod``, and any
            unrecognised value) render JSON; ``local``/``test``/``development`` render
            the human console. Pass it explicitly when the consumer's setting isn't named
            ``ENV`` (e.g. sprout-api's ``ENVIRONMENT``) — it takes precedence over the
            ``ENV`` env var. When ``None`` (the default), falls back to reading ``ENV``.
            Symmetric with ``init_sentry(environment=...)``.
        extra_processors: structlog processors inserted before rendering — the
            per-service extension point (e.g. a redaction or dict-repr filter).
        forward_to_sentry: also emit events to Sentry Logs (pair with `init_sentry`).
    """
    env = environment if environment is not None else os.getenv("ENV", "development")
    # Per the workspace ENV convention (local|dev|prod|test): only `local` is a dev
    # machine (console); `dev` and `prod` are both *hosted* and emit JSON. `test` (the
    # suite) and the legacy `development` default stay console. Anything else is treated
    # as hosted → JSON, so an unrecognised hosted env still gets machine-parseable logs.
    # "production" is kept as a console-exempt alias for callers already passing it.
    _console_envs = {"local", "test", "development"}
    is_prod = env.lower() not in _console_envs
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
        # `color_message` is uvicorn's ANSI-coloured duplicate of the message, passed
        # as a log `extra`; it's pure noise once bridged into our format.
        for key in ("_record", "_from_structlog", "_logger", "_name", "color_message"):
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

    # Route server loggers through the root handler so they render in our format.
    for name in _SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        server_logger.handlers = []
        server_logger.propagate = True

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

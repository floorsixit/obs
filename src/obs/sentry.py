"""Sentry init — guarded, errors-only, PII off, Sentry Logs on."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Any

import sentry_sdk


def init_sentry(
    dsn: str | None,
    *,
    environment: str,
    server_name: str,
    release: str | None = None,
    integrations: Sequence[Any] | None = None,
    disabled_integrations: Sequence[Any] | None = None,
    traces_sample_rate: float = 0.0,
    before_send: Callable[..., Any] | None = None,
    before_send_log: Callable[..., Any] | None = None,
    debug: bool = False,
) -> bool:
    """Initialise Sentry if a DSN is set and we're not under pytest.

    Errors-only by default (`traces_sample_rate=0`), PII off, Sentry Logs on
    (`enable_logs=True`) so `configure_logging`'s forwarder works. Returns True iff
    Sentry was initialised.

    The pytest guard is a *correctness* guard, not hygiene: a service's app module is
    imported with the dev `.env` loaded during tests, so without it every
    test-triggered 500 ships to the live project.

    App-specific integrations (`FastApiIntegration`, …) are passed by the caller via
    `integrations`; noisy ones via `disabled_integrations`; custom scrubbing via
    `before_send` / `before_send_log`.
    """
    if not dsn or "pytest" in sys.modules:
        return False

    kwargs: dict[str, Any] = {
        "dsn": dsn,
        "environment": environment,
        "server_name": server_name,
        "traces_sample_rate": traces_sample_rate,
        "send_default_pii": False,
        "enable_logs": True,
        "debug": debug,
    }
    if release is not None:
        kwargs["release"] = release
    if integrations is not None:
        kwargs["integrations"] = list(integrations)
    if disabled_integrations is not None:
        kwargs["disabled_integrations"] = list(disabled_integrations)
    if before_send is not None:
        kwargs["before_send"] = before_send
    if before_send_log is not None:
        kwargs["before_send_log"] = before_send_log

    sentry_sdk.init(**kwargs)
    return True

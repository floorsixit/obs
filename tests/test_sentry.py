import sys

import pytest
import sentry_sdk

from obs import init_sentry

_DSN = "https://k@o123.ingest.sentry.io/1"


def test_no_dsn_is_noop():
    assert init_sentry(None, environment="development", server_name="t") is False
    assert init_sentry("", environment="development", server_name="t") is False


def test_pytest_guard_always_noops():
    # We are running under pytest, so init must refuse even with a real-looking DSN —
    # this is what stops the suite shipping events to the live project.
    assert "pytest" in sys.modules
    assert init_sentry(_DSN, environment="production", server_name="t") is False


@pytest.fixture
def captured_init(monkeypatch):
    """Bypass the pytest guard and capture the kwargs init_sentry hands to sentry_sdk.init.

    The guard refuses while "pytest" is in sys.modules; remove it for the call (restored at
    teardown) and stub sentry_sdk.init so nothing reaches the network.
    """
    captured: dict = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: captured.update(kw))
    monkeypatch.delitem(sys.modules, "pytest")
    return captured


def test_init_applies_security_defaults(captured_init):
    # These defaults are the whole reason obs owns this: PII off, errors-only, logs on.
    assert init_sentry(_DSN, environment="prod", server_name="svc") is True
    assert captured_init["send_default_pii"] is False
    assert captured_init["traces_sample_rate"] == 0.0
    assert captured_init["enable_logs"] is True
    assert captured_init["environment"] == "prod"
    assert captured_init["server_name"] == "svc"
    # Optional args are omitted (not passed as None) when not supplied.
    assert "release" not in captured_init
    assert "integrations" not in captured_init
    assert "before_send" not in captured_init


def test_init_forwards_optional_args(captured_init):
    sentinel = object()
    assert (
        init_sentry(
            _DSN,
            environment="prod",
            server_name="svc",
            release="v1.2.3",
            integrations=[sentinel],
            disabled_integrations=[sentinel],
            traces_sample_rate=0.25,
            before_send=lambda event, hint: event,
            before_send_log=lambda record, hint: record,
            debug=True,
        )
        is True
    )
    assert captured_init["release"] == "v1.2.3"
    assert captured_init["integrations"] == [sentinel]
    assert captured_init["disabled_integrations"] == [sentinel]
    assert captured_init["traces_sample_rate"] == 0.25
    assert captured_init["debug"] is True
    assert callable(captured_init["before_send"])
    assert callable(captured_init["before_send_log"])

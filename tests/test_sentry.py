import sys

from obs import init_sentry


def test_no_dsn_is_noop():
    assert init_sentry(None, environment="development", server_name="t") is False
    assert init_sentry("", environment="development", server_name="t") is False


def test_pytest_guard_always_noops():
    # We are running under pytest, so init must refuse even with a real-looking DSN —
    # this is what stops the suite shipping events to the live project.
    assert "pytest" in sys.modules
    assert init_sentry("https://k@o123.ingest.sentry.io/1", environment="production", server_name="t") is False

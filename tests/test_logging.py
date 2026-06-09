import json
import logging

import structlog

from obs import bind_context, configure_logging, get_logger


def _last_json(capsys):
    line = capsys.readouterr().err.strip().splitlines()[-1]
    return json.loads(line)


def test_json_render_in_prod(capsys, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    configure_logging("test-svc", forward_to_sentry=False)
    get_logger().info("hello_event", k=1)
    rec = _last_json(capsys)
    assert rec["event"] == "hello_event"
    assert rec["service"] == "test-svc"
    assert rec["k"] == 1
    assert rec["level"] == "info"


def test_server_loggers_render_through_root(capsys, monkeypatch):
    # uvicorn/gunicorn install their own handlers with propagate=False when run via
    # their CLIs. configure_logging (which runs after, on app import) must neutralize
    # them so their output flows through the root obs handler and renders in our format.
    monkeypatch.setenv("ENV", "production")
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [logging.StreamHandler()]
        lg.propagate = False

    configure_logging("test-svc", forward_to_sentry=False)

    err = logging.getLogger("uvicorn.error")
    assert err.handlers == []
    assert err.propagate is True
    # A WARNING+ event on a server logger now renders via the root obs JSON handler,
    # and uvicorn's `color_message` extra is dropped as noise.
    err.warning("server_warn", extra={"color_message": "server_warn (coloured)"})
    rec = _last_json(capsys)
    assert rec["event"] == "server_warn"
    assert rec["service"] == "test-svc"
    assert "color_message" not in rec


def test_sentry_origin_logs_not_forwarded(monkeypatch):
    # Recursion guard: the Sentry SDK logs its own activity ("Sending envelope") via
    # stdlib logging. Those records get bridged into our pipeline; forwarding them back
    # into Sentry Logs creates an exponential feedback loop (each forward makes the SDK
    # log again). The forwarder must skip records originating from the sentry_sdk logger.
    import sentry_sdk.logger as sl

    from obs.logging import _sentry_log_processor

    calls = []
    for lvl in ("trace", "debug", "info", "warning", "error", "fatal"):
        monkeypatch.setattr(sl, lvl, lambda *a, **k: calls.append(a), raising=False)

    sdk_rec = logging.LogRecord("sentry_sdk.errors", logging.DEBUG, __file__, 1, "Sending envelope", None, None)
    _sentry_log_processor(None, None, {"event": "Sending envelope", "level": "debug", "_record": sdk_rec})
    assert calls == []  # SDK's own log must NOT be forwarded

    app_rec = logging.LogRecord("app.svc", logging.INFO, __file__, 1, "real", None, None)
    _sentry_log_processor(None, None, {"event": "real_event", "level": "info", "_record": app_rec})
    assert calls and calls[0][0] == "real_event"  # genuine app log still forwards


def test_contextvars_flow_to_events(capsys, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    configure_logging("test-svc", forward_to_sentry=False)
    structlog.contextvars.clear_contextvars()
    bind_context(request_id="abc123")
    get_logger().info("ctx_event")
    rec = _last_json(capsys)
    assert rec["request_id"] == "abc123"
    structlog.contextvars.clear_contextvars()

import json

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


def test_contextvars_flow_to_events(capsys, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    configure_logging("test-svc", forward_to_sentry=False)
    structlog.contextvars.clear_contextvars()
    bind_context(request_id="abc123")
    get_logger().info("ctx_event")
    rec = _last_json(capsys)
    assert rec["request_id"] == "abc123"
    structlog.contextvars.clear_contextvars()

# obs

Shared observability — structlog logging + Sentry, standardized across Python services.
A single canonical logging + Sentry setup so each service doesn't hand-roll its own:
fix here, bump the tag, and consumers pick it up on `uv sync`.

## Install

```bash
uv add "git+https://github.com/pjvv/obs@v0.1.0"
```

Pin a tag; `uv.lock` records the commit, so the consuming repo stays reproducible.

## Use

```python
from obs import configure_logging, init_sentry, get_logger, bind_context

configure_logging(service="core")                 # console in dev, JSON in prod (ENV)
init_sentry(                                       # no-op without a DSN / under pytest
    settings.sentry_dsn,
    environment=settings.env,
    server_name="core",
    release=settings.release,                      # git SHA — maps errors to a deploy
    integrations=[FastApiIntegration(), AsyncioIntegration()],
)

log = get_logger()
log.info("request_handled", path="/api/v1/accounts")   # event name + kwargs, no f-strings
```

In middleware, bind per-request context once — it flows to every later log:

```python
bind_context(request_id=request_id)
```

## What it standardizes

- **Logging:** `ENV`-driven console/JSON, `LOG_LEVEL`, ISO timestamps, a `service`
  field, stdlib bridge (httpx/uvicorn/sqlalchemy), noisy-logger silencing, and
  structlog → Sentry Logs forwarding.
- **Sentry:** DSN+pytest guarded, `traces_sample_rate=0`, `send_default_pii=False`,
  `enable_logs=True`.

## Extension points (per-service needs, without forking)

- `configure_logging(..., extra_processors=[...])` — inject processors (redaction, a
  dict-repr filter, …).
- `init_sentry(..., integrations=[...], disabled_integrations=[...], before_send=...,`
  `before_send_log=...)` — app integrations and custom scrubbing.

## Dev

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ty check
```

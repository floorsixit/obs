# CLAUDE.md — obs

Shared observability package: structlog logging + Sentry, standardized across Python
services. A single canonical logging + Sentry setup so each service doesn't hand-roll
its own.

The code carries PII-scrubbing and a pytest-Sentry guard, where a *divergent* copy
would be a security bug, not just drift — which is why it lives in one shared package.

## Layout

- `src/obs/logging.py` — `configure_logging`, `get_logger`, `bind_context`
- `src/obs/sentry.py` — `init_sentry`
- public API re-exported from `src/obs/__init__.py`

## Commands

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check
```

## Release & consume

Tag a release; consumers pin it:

```bash
git tag v0.1.0 && git push --tags
# in a consumer repo:
uv add "git+https://github.com/pjvv/obs@v0.1.0"
```

**Keep the public API stable** — `configure_logging` / `init_sentry` signatures are a
contract across every consuming service. Add via keyword-only params with defaults;
don't break positional/required args. Per-service needs go through the extension hooks
(`extra_processors`, `integrations`, `before_send`), never a fork.

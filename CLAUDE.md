# CLAUDE.md — obs

Shared observability package for `~/dev/homework`: structlog logging + Sentry,
standardized across the Python services. The **canonical implementation** of the
workspace `CONVENTIONS.md` › Logging and › Error tracking (Sentry) — it replaces the
per-repo copied `logging_config.py`.

This is the workspace's **one deliberate shared package** (an explicit exception to
"repos are self-contained / no shared package") — justified because the code carries
PII-scrubbing and the pytest-Sentry guard, where a *divergent* copy is a security bug,
not just drift.

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
uv add "git+ssh://git@github.com/pjvv/obs@v0.1.0"
```

**Keep the public API stable** — `configure_logging` / `init_sentry` signatures are a
contract across every consuming service. Add via keyword-only params with defaults;
don't break positional/required args. Per-service needs go through the extension hooks
(`extra_processors`, `integrations`, `before_send`), never a fork.

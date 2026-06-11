> **PR title must be a valid Conventional Commit** — `<type>(<scope>)?: <summary>`
> (`feat` → minor · `fix`/`perf` → patch · `docs`/`chore`/`ci`/`refactor`/`test`/`build`/`style` → no release;
> `!` after the type or a `BREAKING CHANGE:` footer → major). We **squash-merge**, so this
> title becomes the commit subject python-semantic-release parses on `main` — a wrong type
> silently ships **no release**. Pre-1.0 (`major_on_zero=false`): a breaking change bumps
> **minor**, not major.

## Summary

<!-- What changed and why. -->

## Checklist

- [ ] PR title is a valid Conventional Commit (see above)
- [ ] Gates ran locally and pass — `ruff check`/`format --check`, `ty check`, `pytest`, `pip-audit` (mirror CI)
- [ ] `CLAUDE.md` / `README.md` updated if behaviour or setup changed

## Public API / breaking change

<!-- obs is a pinned shared dependency: configure_logging / init_sentry / get_logger /
     bind_context signatures are a contract across every consumer. Adding via keyword-only
     params with defaults is non-breaking. If this DOES break the API, mark the commit
     `<type>!:` or add a BREAKING CHANGE: footer, and spell out the consumer migration path.
     Delete this section if the public API is untouched. -->

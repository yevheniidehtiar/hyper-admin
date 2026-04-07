---
type: story
id: MWniP9cYATma
title: "feat(core): add pydantic-settings dependency and HyperAdminSettings class"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:M
  - area:settings
estimate: null
epic_ref: null
github:
  issue_number: 375
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7a72b8306bdaa82d5b7756ae0859a64ea1ddfcca46c70d025095f20be77342c8
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T09:04:12Z
updated_at: 2026-03-31T16:57:54Z
---

## Context

Django-like centralized settings via `pydantic-settings` BaseSettings. Currently `db.py` has hardcoded `sqlite_url` and `echo=True`, session secret has unsafe fallback `"hyperadmin-default-secret"`, and `Admin.__init__()` has 10 parameters with no unified configuration.

## Scenarios

**Scenario: settings load from environment variables**
  Given `HYPERADMIN_DATABASE_URL=sqlite+aiosqlite:///prod.db` is set
  When  `HyperAdminSettings()` is instantiated
  Then  `settings.database_url == "sqlite+aiosqlite:///prod.db"`

**Scenario: settings load from .env file**
  Given a `.env` file contains `HYPERADMIN_SECRET_KEY=my-secret`
  When  `HyperAdminSettings()` is instantiated
  Then  `settings.secret_key == "my-secret"`

**Scenario: explicit kwargs override env vars**
  Given `HYPERADMIN_SECRET_KEY=env-value` in environment
  When  `HyperAdminSettings(secret_key="explicit")` is created
  Then  `settings.secret_key == "explicit"`

**Scenario: sensible defaults without any configuration**
  Given no env vars or .env file
  When  `HyperAdminSettings()` is instantiated
  Then  all fields have safe defaults and no errors

## Acceptance criteria

- [ ] `pydantic-settings>=2.0` added to `[project.dependencies]` in `pyproject.toml`
- [ ] New file: `src/hyperadmin/core/settings.py`
- [ ] `HyperAdminSettings(BaseSettings)` with fields: site_title, site_header, secret_key, database_url, debug, auto_discover, theme, items_per_page, date_format, datetime_format
- [ ] `env_prefix="HYPERADMIN_"` via `model_config = SettingsConfigDict(...)`
- [ ] `.env` file support
- [ ] Sensible defaults for all fields
- [ ] Unit tests in `tests/unit/test_settings.py`

## Files likely affected

- `pyproject.toml` (add dependency)
- `src/hyperadmin/core/settings.py` (new)
- `src/hyperadmin/core/__init__.py` (export)
- `tests/unit/test_settings.py` (new)

## Dependencies

Depends on: #374 (SDD approval)

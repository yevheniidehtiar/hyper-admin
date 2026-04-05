---
type: story
id: a5yDtmTgFwP0
title: "test: settings loading, validation, env override"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:M
  - area:settings
estimate: null
epic_ref: null
github:
  issue_number: 379
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:452d85aa59b9af52b41a9707f9fdf01495d0ff9f060251ebd267e67d39a4c9ef
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T09:09:37Z
updated_at: 2026-03-31T19:59:04Z
---

## Context

Comprehensive test suite for HyperAdminSettings covering env var loading, .env file support, validation, and integration with Admin class.

## Scenarios

**Scenario: env vars with HYPERADMIN_ prefix are loaded**
  Given `HYPERADMIN_SITE_TITLE=My App` in environment
  When  `HyperAdminSettings()` is instantiated
  Then  `settings.site_title == "My App"`

**Scenario: invalid theme value rejected**
  Given `HYPERADMIN_THEME=neon` in environment
  When  `HyperAdminSettings()` is instantiated
  Then  a `ValidationError` is raised

**Scenario: all defaults are valid**
  Given clean environment (no HYPERADMIN_* vars)
  When  `HyperAdminSettings()` is instantiated
  Then  all fields have values and pass validation

## Acceptance criteria

- [ ] Tests for env var loading (all fields)
- [ ] Tests for .env file loading
- [ ] Tests for validation (invalid theme, empty database_url, etc.)
- [ ] Tests for default values
- [ ] Tests for Admin integration (settings flows through to behavior)

## Files likely affected

- `tests/unit/test_settings.py` (new or extend)

## Dependencies

Depends on: #375, #376

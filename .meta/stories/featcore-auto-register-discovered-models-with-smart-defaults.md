---
type: story
id: pYq6pMx53x35
title: "feat(core): auto-register discovered models with smart defaults"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - auto-discovery
  - agent-task
  - area:core
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 370
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a719f9043a9324b385828dc11b4ab6481d86db23383b4b4f10ca4950b91dc28f
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T08:58:20Z
updated_at: 2026-03-31T20:43:36Z
---

## Context

Connects discovery (#367) with smart defaults (#364, #365, #366). For each discovered model not already in `site._registry`, generates `AdminOptions` via introspection and calls `site.register()`.

## Scenarios

**Scenario: zero-config mount registers all user models**
  Given an app with 3 SQLModel table models and no explicit `site.register()` calls
  When  `Admin(app, engine=engine).mount("/admin")` is called
  Then  all 3 models appear in `site._registry`
  And   each model has AdminOptions derived from field introspection

**Scenario: explicit registration is not overwritten**
  Given Product is explicitly registered with `AdminOptions(can_delete=False)`
  When  auto-discovery runs
  Then  Product's AdminOptions still has `can_delete=False`

## Acceptance criteria

- [ ] `_auto_register_models()` method in `core/app.py`
- [ ] Discovered models filtered by `__module__` — exclude `hyperadmin.*` internal models
- [ ] Each model gets AdminOptions with inferred list_display, search_fields, list_filter
- [ ] Models already in `site._registry` are skipped silently
- [ ] Abstract SQLModel classes (no `table=True`) excluded
- [ ] Unit tests for registration logic

## Files likely affected

- `src/hyperadmin/core/app.py`
- `tests/unit/test_auto_register.py` (new)

## Dependencies

Depends on: #364, #365, #366, #367

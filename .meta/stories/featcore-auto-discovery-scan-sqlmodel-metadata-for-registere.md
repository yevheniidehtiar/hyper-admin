---
type: story
id: EatZA9_JCwQ8
title: "feat(core): auto-discovery — scan SQLModel metadata for registered models"
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
  issue_number: 367
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b1189c67e76d5354c7df08dbb25589bb352b040f1db33a7328694f2714ff9865
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T08:50:24Z
updated_at: 2026-03-31T20:43:35Z
---

## Context

`discover_sqlmodel_models()` walks SQLModel's metadata registry and returns model classes. Filters out HyperAdmin internal models by `__module__` prefix and abstract models without `table=True`.

## Scenarios

**Scenario: discovery finds all user-defined table models**
  Given 3 SQLModel table models defined in user code
  When  `discover_sqlmodel_models()` is called
  Then  all 3 models are returned

**Scenario: HyperAdmin internal models are excluded**
  Given User, Group, Permission models from `hyperadmin.auth.models`
  When  `discover_sqlmodel_models()` is called
  Then  none of the internal models are returned

**Scenario: abstract models without table=True are excluded**
  Given a SQLModel base class without `table=True`
  When  `discover_sqlmodel_models()` is called
  Then  the abstract class is not in the results

## Acceptance criteria

- [ ] `discover_sqlmodel_models() -> list[type]` in `core/introspection.py`
- [ ] Walks `SQLModel.metadata.tables` and maps to model classes
- [ ] Filters by `__module__` prefix — excludes `hyperadmin.*`
- [ ] Excludes abstract models (no `__tablename__`)
- [ ] Unit tests with mock models

## Files likely affected

- `src/hyperadmin/core/introspection.py`
- `tests/unit/test_introspection.py`

## Dependencies

Depends on: #363

## Notes for implementer

SQLModel shares a single global metadata registry — no per-app isolation. Filter by `model.__module__` not starting with `hyperadmin`. Third-party models excluded unless explicitly registered.

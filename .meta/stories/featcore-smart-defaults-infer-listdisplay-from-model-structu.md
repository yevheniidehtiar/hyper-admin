---
type: story
id: t-KW5DD232_-
title: "feat(core): smart defaults — infer list_display from model structure"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 364
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:1651c81509ea1af71a9257c088ff95175db07c491d7f044f9a6ec069317abfaa
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T08:46:58Z
updated_at: 2026-03-31T20:43:34Z
---

## Context

Auto-select 3-5 important fields for list view display via heuristics on field types and names. Part of the zero-config experience.

## Scenarios

**Scenario: list_display infers key fields**
  Given a model with fields: id, name, email, created_at, is_active, bio
  When  `infer_list_display(model)` is called
  Then  the result contains id, name, email, created_at (≤5 fields)
  And   bio (long text) is excluded

**Scenario: model with only id field**
  Given a model with only an `id` field
  When  `infer_list_display(model)` is called
  Then  the result is `["id", "__str__"]`

## Acceptance criteria

- [ ] `infer_list_display()` returns ≤5 fields ordered by priority
- [ ] Priority: id > name/title > email > created_at/updated_at > status/is_active > other short fields
- [ ] Long text fields (Text type, bio, description) excluded
- [ ] Unit tests covering mixed field models, minimal models, and >5 candidate fields

## Files likely affected

- `src/hyperadmin/core/introspection.py`
- `tests/unit/test_introspection.py`

## Dependencies

Depends on: #363

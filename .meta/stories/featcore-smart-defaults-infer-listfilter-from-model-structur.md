---
type: story
id: RZL7i3OM4h1j
title: "feat(core): smart defaults — infer list_filter from model structure"
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
  issue_number: 366
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:2e9f8ac85f795fc7828c823abf464e50f83d70690557767d7a70e76181fb1f45
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T08:47:53Z
updated_at: 2026-03-31T20:43:34Z
---

## Context

Auto-include Boolean, Enum, and ForeignKey fields for sidebar filtering.

## Scenarios

**Scenario: list_filter infers boolean and enum fields**
  Given a model with fields: is_active (bool), status (Enum), name (str), category_id (int FK)
  When  `infer_list_filter(model)` is called
  Then  the result contains is_active, status, category_id
  And   name is excluded

**Scenario: model with no filterable fields**
  Given a model with only string and numeric fields
  When  `infer_list_filter(model)` is called
  Then  the result is `[]`

## Acceptance criteria

- [ ] `infer_list_filter()` returns bool, enum, FK field names
- [ ] String, text, numeric-only fields excluded
- [ ] Returns `[]` when no filterable fields exist
- [ ] Unit tests

## Files likely affected

- `src/hyperadmin/core/introspection.py`
- `tests/unit/test_introspection.py`

## Dependencies

Depends on: #363

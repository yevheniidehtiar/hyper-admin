---
type: story
id: qN5QGIZsKmPX
title: "feat(views): display inferred field labels in list/detail views"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 369
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0111625912c9c88c7629cba5c1d8cbf58f9e268bdcaffaa808a94a115d3bcd36
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T08:53:06Z
updated_at: 2026-03-31T20:43:36Z
---

## Context

Field names like `user_id` and `created_at` should render as "User" and "Created At" in list and detail views. Consolidates field-label generation into `core/display.py`, superseding inline logic in `views/forms.py` and `core/discovery.py:29`.

## Scenarios

**Scenario: field name user_id renders as label "User"**
  Given a model with a FK field named `user_id`
  When  the list view renders the column header
  Then  the header displays "User" not "user_id"

**Scenario: field name created_at renders as label "Created At"**
  Given a model with a field named `created_at`
  When  the list view renders the column header
  Then  the header displays "Created At"

**Scenario: simple field name renders title-cased**
  Given a model with a field named `email`
  When  the list view renders the column header
  Then  the header displays "Email"

## Acceptance criteria

- [ ] `get_field_label(field_name: str) -> str` in `core/display.py`
- [ ] Strips `_id` suffix for FK fields → title case the remainder
- [ ] Replaces `_` with space → title case for all other fields
- [ ] Used in list view column headers and detail view field labels
- [ ] Supersedes inline label logic in `views/forms.py` and `core/discovery.py:29`
- [ ] Unit tests

## Files likely affected

- `src/hyperadmin/core/display.py` — add `get_field_label()`
- `src/hyperadmin/views/dynamic.py` — use new label function
- `tests/unit/test_display.py`

## Dependencies

Depends on: #363

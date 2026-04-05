---
type: story
id: FIVTlERrLUSZ
title: "feat(core): smart defaults — infer search_fields from model structure"
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
  issue_number: 365
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:bbee2a852288eefcf8c899f79dac3c1a520e367fe537760c9234f26cbf7036e5
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T08:47:13Z
updated_at: 2026-03-31T20:43:34Z
---

## Context

Auto-include String/Email/Text fields for search, skip FK/M2M/binary/numeric fields.

## Scenarios

**Scenario: search_fields infers string fields**
  Given a model with fields: id (int), name (str), email (str), is_active (bool), category_id (int FK)
  When  `infer_search_fields(model)` is called
  Then  the result contains name and email
  And   id, is_active, category_id are excluded

**Scenario: model with no string fields**
  Given a model with only numeric and boolean fields
  When  `infer_search_fields(model)` is called
  Then  the result is `[]`

## Acceptance criteria

- [ ] `infer_search_fields()` returns string/email/text field names
- [ ] FK, numeric, boolean, binary fields excluded
- [ ] Returns `[]` when no string fields exist
- [ ] Unit tests

## Files likely affected

- `src/hyperadmin/core/introspection.py`
- `tests/unit/test_introspection.py`

## Dependencies

Depends on: #363

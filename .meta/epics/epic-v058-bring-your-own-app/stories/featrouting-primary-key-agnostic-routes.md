---
type: story
id: st-v058-byoa-02
title: "feat(routing): primary-key-agnostic routes (UUID / str / int)"
status: todo
priority: critical
assignee: null
labels:
  - planned
  - area:core
  - size:M
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Replace `{item_id:int}` path params in `routing.py` with a converter derived from the model's primary key type; coerce in views via the adapter. Update `views/forms.py` / `views/dynamic.py` inline parent/child PK typing.

## Acceptance Criteria

- [ ] Detail/update/delete/inline/action/file routes resolve UUID and string PKs
- [ ] Existing int-PK URLs unchanged
- [ ] Unit + E2E coverage with a UUID-keyed model

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)

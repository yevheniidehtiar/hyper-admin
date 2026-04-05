---
type: story
id: b4l0oHYX4_-Y
title: "test: unit tests for FieldsetSpec and AdminOptions.fieldsets"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:S
estimate: null
epic_ref:
  id: HMxZRjunTlAA
github:
  issue_number: 189
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:778e4dd2aca0777f0e30c440d4502e24e367734ddda8841bb6ea656f88eb3ac6
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:34:41Z
updated_at: 2026-03-28T19:45:59Z
---

> **Part of:** #38
> **Depends on:** #188

## Acceptance Criteria
- [ ] `tests/unit/test_fieldsets.py`: `FieldsetSpec` construction, field membership, `collapsible` default False
- [ ] `AdminOptions` stores and returns `fieldsets` list correctly
- [ ] `poe test:unit` green

## Files
- `tests/unit/test_fieldsets.py` (new)


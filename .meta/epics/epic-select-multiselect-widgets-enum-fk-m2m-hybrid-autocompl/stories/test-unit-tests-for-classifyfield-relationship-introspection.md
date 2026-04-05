---
type: story
id: DC3OxzLURYw4
title: "test: unit tests for classify_field() relationship introspection"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:S
estimate: null
epic_ref:
  id: IYTFerusYXD-
github:
  issue_number: 181
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:72f3bc5152cae6563dd90af1f87d73c37a9fca805f47f136b99391a36478d310
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:33:37Z
updated_at: 2026-03-26T23:50:22Z
---

> **Part of:** #159
> **Depends on:** #162

## Acceptance Criteria
- [ ] `tests/unit/test_core_field_classification.py` covers: Enum, list[Enum], FK, M2M, list[str] hybrid, plain str → None
- [ ] Mocks SQLAlchemy mapper — no real DB required
- [ ] `poe test:unit` green

## Files
- `tests/unit/test_core_field_classification.py` (new)


---
type: story
id: FwsUab8EHd2L
title: "test: unit tests for SQLModelAdapter.get_choices() with N+1 assertion"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:M
estimate: null
epic_ref:
  id: -TGq_yaQZtX_
github:
  issue_number: 182
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d9d82c6abdf296ae507ba77bc63c231e8fa61d2219be9d8be329bc304b64304b
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-25T13:33:39Z
updated_at: 2026-03-26T23:51:06Z
---

> **Part of:** #159
> **Depends on:** #161

## Acceptance Criteria
- [ ] `tests/unit/test_adapter_choices.py`: FK single query, M2M join query, pagination limits
- [ ] SQLAlchemy event query counter asserts no N+1
- [ ] `get_choices(**filters)` for cascading covered
- [ ] `poe test:unit` green

## Files
- `tests/unit/test_adapter_choices.py` (new or extend existing)


---
type: story
id: lllCnPmwCeWE
title: "feat(core): JsonApiAdapter protocol and response envelope schema"
status: todo
priority: medium
assignee: null
labels:
  - area:core
  - agent:claude
  - size:M
estimate: null
epic_ref:
  id: 0Ds0szEo93g1
github:
  issue_number: 197
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a1f36dd198cc5aff3c987dc875a28eb4828b34373d2533d6db1b1481ef3f8423
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-25T13:41:51Z
updated_at: 2026-03-30T20:51:48Z
---

> **Part of:** #76
> **No dependencies (base task)**

## Acceptance Criteria
- [ ] `core/adapters.py`: `JsonApiAdapter` extends `BaseAdapter` with `to_dict(record) -> dict` method
- [ ] Response envelope schema: `{data: [...], meta: {total, page, page_size}}`
- [ ] Exported from `core/__init__.py`
- [ ] No ORM imports in `core/` — pure protocol
- [ ] `mypy` clean

## Files
- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/core/__init__.py`


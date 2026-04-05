---
type: story
id: _DaaHW58fxQn
title: "feat(adapters): implement keyset pagination in SQLModelAdapter"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:adapters
  - agent:claude
  - size:L
  - performance
estimate: null
epic_ref:
  id: bz_SWmq9yUG6
github:
  issue_number: 228
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7db36df448dd21ad7a8d01681684200b9d4ddca93ee23046af66d5cef761036d
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:41:24Z
updated_at: 2026-03-27T00:41:24Z
---

## Context
Part of Epic #211 (A4: Keyset/cursor pagination).

## Acceptance criteria
- [ ] When `pagination_mode="keyset"`, uses `WHERE id > cursor ORDER BY id LIMIT page_size`
- [ ] Cursor encoded/decoded as opaque string (base64 of PK value)
- [ ] Support for compound sort keys (e.g., created_at + id)
- [ ] Correct handling of sort direction (ASC/DESC)
- [ ] Falls back to offset mode when `pagination_mode="offset"`
- [ ] All tests from A4.1 pass

## Files
- `src/hyperadmin/adapters/sqlmodel.py`

## Dependencies
- Blocked by: #227 (A4.2 core contract)
- Blocking: A4.4

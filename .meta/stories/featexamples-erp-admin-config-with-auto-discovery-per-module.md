---
type: story
id: bgxBIBjm0Wim
title: "feat(examples): ERP admin config with auto-discovery per module"
status: done
priority: medium
assignee: null
labels:
  - in-progress
  - agent-task
  - area:examples
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 193
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7d8695c1a45b9ad55c9b2aea012833ec0e25c0e57c2f6dbff2638923d83a5b62
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:41:13Z
updated_at: 2026-03-30T16:09:12Z
---

> **Part of:** #172
> **Depends on:** #192

## Acceptance Criteria
- [ ] `admin.py` in each module registers all models via `@admin.register`
- [ ] `column_list`, `search_fields`, `list_filter` configured per model
- [ ] All modules auto-discovered on app startup (no manual import required)
- [ ] Admin renders list + detail pages for all 9 models

## Files
- `examples/erp/contacts/admin.py`
- `examples/erp/sales/admin.py`
- `examples/erp/purchases/admin.py`
- `examples/erp/accounting/admin.py`
- `examples/erp/main.py`


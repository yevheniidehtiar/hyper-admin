---
type: story
id: cSPYK64jqfU7
title: "feat(examples): ERP Faker seeding script with double-entry journal lines"
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
  issue_number: 194
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:6bf681375be6984c716ede6c622db6bd915ce1bb11e22e249cfbeee5a7c5994a
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:41:16Z
updated_at: 2026-03-30T16:10:19Z
---

> **Part of:** #172
> **Depends on:** #192

## Acceptance Criteria
- [ ] `examples/erp/seed.py` generates: 100+ contacts, 500+ invoices, 800+ bills, linked double-entry journal lines
- [ ] Script is idempotent (re-run safe — clears and re-seeds)
- [ ] Runs via: `uv run python examples/erp/seed.py`
- [ ] Completes in < 30s

## Files
- `examples/erp/seed.py` (new)


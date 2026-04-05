---
type: story
id: f5ZGxHqVPrjd
title: "feat(examples): Annual P&L custom report view in ERP admin"
status: done
priority: medium
assignee: null
labels:
  - in-progress
  - agent-task
  - area:examples
  - agent:claude
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 195
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5096b13528a934a924084859286255bf4f868a523ab9a3bc8e4e78cf60e99e86
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:41:18Z
updated_at: 2026-03-30T20:48:27Z
---

> **Part of:** #172
> **Depends on:** #192, #193

## Acceptance Criteria
- [ ] Custom FastAPI route registered within HyperAdmin router at `/admin/reports/profit-loss`
- [ ] Queries `JournalLine` aggregates for revenue / expenses / net per calendar year
- [ ] Renders in admin layout (Jinja2 template extends `base.html`)
- [ ] Accessible from admin sidebar nav under "Reports"
- [ ] Correct totals verified against seeded data

## Files
- `examples/erp/reports/views.py` (new)
- `examples/erp/reports/admin.py` (new)
- `examples/erp/templates/reports/profit_loss.html` (new)


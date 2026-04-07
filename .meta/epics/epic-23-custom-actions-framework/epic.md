---
type: epic
id: kR3DYwg4B6e2
title: "Epic 2.3: Custom Actions Framework"
status: done
priority: medium
owner: null
labels:
  - enhancement
  - core
  - actions
  - framework
milestone_ref:
  id: EVI7ja6oi2TX
github:
  issue_number: 41
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a289eb09e4be0133c3f2e443fdc24c61c25a3c25d751389ccd1026dd6d533f93
  synced_at: 2026-04-07T17:23:23.789Z
created_at: 2025-08-24T20:08:13Z
updated_at: 2026-03-28T19:45:08Z
---

## Epic: Custom Actions Framework

Part of milestone: **Phase 2: Core Feature Parity**

### Goal
Allow developers to register custom per-record and bulk actions on ModelView classes, exposed as POST endpoints and rendered as buttons in the detail view.

### Dependency Chain

```
ActionDef + @action decorator (core/actions.py)
  └─ Wire POST endpoint in DynamicModelView
       └─ #70 Actions UI in detail view (buttons + HTMX)
```

### Sub-issues
- [ ] #69 Design actions framework (core protocol: `ActionDef`, `@action` decorator)
- [ ] #70 Actions UI in detail view (`data-testid="action-{name}-btn"`)

### Missing tasks (to be created)
- `feat(views)`: wire `POST /admin/{model}/{id}/action/{name}` endpoint
- `test`: unit tests for `ActionDef` and decorator registration
- `test(e2e)`: action button triggers handler and redirects

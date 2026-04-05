---
type: epic
id: HMxZRjunTlAA
title: "Epic 2.2: Form & Layout Control"
status: done
priority: medium
owner: null
labels:
  - enhancement
  - frontend
  - forms
  - fieldsets
  - layouts
milestone_ref:
  id: G-6OAukVeUo7
github:
  issue_number: 38
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:4eed4a86bd4adfe2e5bdd81ff89034bdc92b30ba0d43555b386e2272c0165c1e
  synced_at: 2026-04-05T09:13:33.558Z
created_at: 2025-08-24T20:07:43Z
updated_at: 2026-03-30T20:50:52Z
---

## Epic: Form & Layout Control

Part of milestone: **Phase 2: Core Feature Parity**

### Goal
Give developers control over form structure: group fields into collapsible fieldsets, define custom grid layouts, and edit related records inline.

### Dependency Chain

```
FieldsetSpec dataclass (core/options.py)
  ├─ #66 Fieldsets in form templates (collapse/expand)
  ├─ #67 Custom form layout (grid positioning)
  └─ #68 Inline models (depends also on #161, #162 from Epic A)
```

### Sub-issues
- [x] #66 Implement fieldsets for grouping fields
- [x] #67 Add support for custom form layouts
- [x] #68 Implement inline models for editing related models

### Missing tasks (to be created)
- `feat(core)`: `FieldsetSpec` dataclass + `AdminOptions.fieldsets`
- `test`: unit tests for `FieldsetSpec`
- `test(e2e)`: fieldset collapse/expand toggle

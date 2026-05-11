---
type: story
id: st-v056-dp-01
title: "feat(core): add PanelDef, @panel decorator, panels registry"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - backend
  - upstream-readiness
  - H4
estimate: null
epic_ref:
  id: ep-v056-dp-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Introduce the panel contract in `src/hyperadmin/core/panels.py` (`PanelDef`,
`@panel`, `collect_panels`) and wire `AdminOptions.panels: list[PanelDef] |
None`. Validate slug uniqueness at registration; derive a default permission
codename `view_{model}_panel_{slug}` per entry.

**Spec:** [`docs/specs/detail-panels.md`](../../../../docs/specs/detail-panels.md)

## Files to Change

- **New:** `src/hyperadmin/core/panels.py`
- **Modified:** `src/hyperadmin/core/options.py` — add `panels`
- **Modified:** `src/hyperadmin/core/__init__.py` — export `PanelDef`, `panel`
- **New:** `tests/unit/test_panels.py`

## Scenarios

```
Scenario: duplicate panel slug raises at registration
  Given AdminOptions(panels=[PanelDef(slug="x", ...), PanelDef(slug="x", ...)])
  When  the model is registered
  Then  ValueError("duplicate panel slug 'x'") is raised

Scenario: default permission codename is derived from model and slug
  Given PanelDef(slug="invoice", label="Invoice", handler=...) on the Order admin
  When  the panel is registered
  Then  the resolved permission is "view_order_panel_invoice"

Scenario: explicit permission overrides the default
  Given PanelDef(slug="invoice", ..., permission="invoice.view")
  Then  the resolved permission is "invoice.view"
```

## Acceptance Criteria

- [ ] `PanelDef` dataclass: `slug`, `label`, `handler`, `icon`, `permission`
- [ ] `@panel` decorator validates handler signature (`(self, request, obj, *, ...)` per resolution of open question)
- [ ] `collect_panels(cls)` returns `list[PanelDef]`
- [ ] Slug uniqueness enforced at registration
- [ ] Default permission codename `view_{model}_panel_{slug}` derived
- [ ] Public exports from `hyperadmin.core` and `hyperadmin`
- [ ] Unit tests cover all three scenarios
- [ ] `poe lint` passes

## Blocked by

- `reviewspec-approve-sdd-detail-panels`

## Parent

- Epic: `epic-v056-detail-panels`

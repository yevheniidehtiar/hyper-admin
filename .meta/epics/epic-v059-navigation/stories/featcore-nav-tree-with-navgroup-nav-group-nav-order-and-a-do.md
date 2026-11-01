---
type: story
id: st-v059-nav-01
title: "feat(core): nav tree with NavGroup, nav_group/nav_order and a domain icon set"
status: backlog
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:core
  - backend
estimate: null
epic_ref:
  id: ep-v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Seam story. Add `core/navigation.py` with `NavGroup` (public), `NavItem`, `NavGroupNode` and `build_nav_tree()`. Read `nav_group`, `nav_order` and `icon` from admin classes (falling back to `app_label`), merge plugin `NavEntry` sections into same-label groups, and publish `nav_tree` as a Jinja global while keeping the flat `nav_items`. Add `nav_groups=` to `HyperAdmin(...)`. Add ~22 Lucide domain icons and regenerate the macro.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **New:** `src/hyperadmin/core/navigation.py`
- **Modified:** `src/hyperadmin/routing.py` (nav block at ~493-584)
- **Modified:** `src/hyperadmin/core/app.py` (`nav_groups=`, plugin nav into the tree)
- **Modified:** `src/hyperadmin/core/model.py`, `src/hyperadmin/__init__.py`
- **New:** `src/hyperadmin/static/icons/*.svg`; **regenerated:** `templates/components/_icons.html`
- **New:** `tests/unit/test_navigation.py`

## Scenarios

```
Scenario: models are grouped and ordered
  Given OrderAdmin(nav_group="Sales", nav_order=1), CustomerAdmin(nav_group="Sales", nav_order=0)
  And   nav_groups=[NavGroup("Sales", order=0), NavGroup("Accounting", order=1)]
  When  build_nav_tree runs
  Then  the "Sales" node lists Customers then Orders, before "Accounting"

Scenario: an ungrouped model lands in the unnamed first group
  Given TagAdmin with no nav_group and no app_label
  When  build_nav_tree runs
  Then  the first node has label None and contains Tags

Scenario: app_label is the default group
  Given site.register(Invoice, app_label="Accounting") without nav_group
  When  build_nav_tree runs
  Then  Invoices is in the "Accounting" node

Scenario: a plugin section merges into the same-label group
  Given a plugin NavEntry with section "Access" and UserAdmin(nav_group="Access")
  When  build_nav_tree runs
  Then  one "Access" node holds both items

Scenario: a model without icon gets the fallback icon
  Given TagAdmin without icon
  When  build_nav_tree runs
  Then  the Tags item icon is "layout-grid"
```

## Acceptance Criteria

- [ ] `NavGroup` exported from `hyperadmin`; `nav_group`, `nav_order`, `icon` documented on the model admin
- [ ] `build_nav_tree()` imports nothing from `views/` (CONSTITUTION §1)
- [ ] `nav_items` global unchanged in shape (host `_sidebar.html` overrides keep working)
- [ ] Case-only duplicate group labels log one warning
- [ ] Icons added from the pinned Lucide release; `scripts/generate_icon_macro.py` rerun
- [ ] Docs: models guide section on grouping and icons
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass

## Notes for Implementer

Hotspot owner for the `routing.py` nav block. Keep `core/navigation.py` under ~300 LOC. Match labels by `str(label)` but keep the `LazyString` for rendering.

## Blocked by

- `reviewspec-approve-navigation-and-list-ux-sdd` (st-v059-nav-00)

## Parent

- Epic: `epic-v059-navigation`

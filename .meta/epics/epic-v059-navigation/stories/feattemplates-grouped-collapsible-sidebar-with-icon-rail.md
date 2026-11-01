---
type: story
id: st-v059-nav-02
title: "feat(templates): grouped collapsible sidebar with icon rail"
status: backlog
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:templates
  - frontend
  - ui
estimate: null
epic_ref:
  id: ep-v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Render `nav_tree` with the AppShell markup: `.ha-nav-group` with an `<h2>` toggle and a `<ul>`, collapsible groups persisted in cookie `ha-nav-collapsed` (server-rendered, no flicker), a desktop icon rail (`ha-sidebar-rail` cookie), segment-prefix active matching and `nav-<key>` / `nav-group-<slug>` test ids. Port the AppShell CSS from `bundle.css`.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **Modified:** `src/hyperadmin/templates/_sidebar.html`, `_base.html` (`data-collapsed`)
- **Modified:** `src/hyperadmin/static/css/_sidebar.css`
- **Modified:** tests listed above; **new:** `tests/e2e/test_sidebar_groups.py`

## Scenarios

```
Scenario: groups render with headings and icons
  Given models grouped into "Sales" and "Accounting"
  When  an admin opens the dashboard
  Then  the sidebar has headings "Sales" and "Accounting" with their items

Scenario: a collapsed group stays collapsed after reload
  Given the "Accounting" group is expanded
  When  the user collapses it and reloads
  Then  the "Accounting" toggle has aria-expanded="false" in the server HTML

Scenario: the rail hides labels but keeps accessible names
  When  the user activates the rail toggle
  Then  nav links keep their accessible names and the rail state survives reload

Scenario: the model of an edit page is active
  When  the user opens /admin/order/42/edit
  Then  the Orders link has aria-current="page" and Order lines does not

Scenario: permission filtering removes empty groups
  Given the user may view none of the "Accounting" models
  When  the user opens the dashboard
  Then  no "Accounting" heading is rendered
```

## Acceptance Criteria

- [ ] Mobile drawer behaviour unchanged (focus trap, Esc, `sidebar-toggle`/`sidebar-close`)
- [ ] RTL: active bar and rail use logical properties
- [ ] Existing sidebar tests updated (`tests/e2e/test_list_view.py:19`, `test_responsive_design.py`, `tests/unit/test_admin_error_pages.py:96,110`)
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass
- [ ] E2E tests map 1:1 to the scenarios, use role/label/test-id locators only, with `# Given / # When / # Then` comments
- [ ] Visual baselines refreshed on Linux (`RESPONSIVE_SNAPSHOTS_UPDATE=1`) where the UI changed
- [ ] Manual test scenarios attached to the PR
- [ ] New `data-testid`s added to the CLAUDE.md reference table

## Notes for Implementer

Hotspot owner for `_sidebar.html` until nav-03 starts. Read the cookie server-side via `request.cookies`; ignore unknown slugs.

## Blocked by

- `featcore-nav-tree-with-navgroup-nav-group-nav-order-and-a-do` (st-v059-nav-01)

## Parent

- Epic: `epic-v059-navigation`

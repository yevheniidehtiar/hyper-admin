---
type: story
id: yusamPwe9nTn
title: "feat(views): render plugin nav entries in the sidebar and sync plugin permissions"
status: done
priority: high
assignee: null
labels:
  - backend
  - frontend
  - size:S
  - planned
  - plugins
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Phase 1b. The sidebar renders `admin.plugins.nav_entries` grouped by `section`
(`None` → "Plugins"), after the model app groups, hiding entries whose `permission`
the user lacks. `PermissionSyncService` syncs `admin.plugins.permissions` next to model
permissions (collision with a model codename → ERROR, skipped). Sidebar links get
`data-testid="sidebar-plugin-link"`.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md) — "Sidebar / nav entries", "Permission codenames"

## Scenarios

**Scenario: plugin nav entry appears for permitted users only**
  Given plugin "reports" adds a nav entry "Reports" with permission "view_report_sales"
  When  a user with that permission opens the dashboard
  Then  the sidebar shows a "Reports" link
  And   a user without it does not see the link

**Scenario: plugin permission shows in the permission system**
  Given plugin "reports" declares "view_report_sales"
  When  permissions are synced
  Then  "view_report_sales" can be assigned to a group

## Blocked by

- `featcore-wire-plugin-ui-seams-into-admin`

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`

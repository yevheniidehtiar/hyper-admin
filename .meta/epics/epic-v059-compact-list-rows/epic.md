---
type: epic
id: ep-v059-list-01
title: "epic(templates): compact list rows with click-to-open and icon delete"
status: backlog
priority: high
owner: null
labels:
  - planned
  - area:views
  - area:templates
  - frontend
  - size:M
milestone_ref:
  id: v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Overview

Drop the View/Edit row buttons. The row opens the edit page for users who may change the record and the detail page for read-only users. Delete becomes a red icon button with a shared confirm dialog, also offered on the detail and edit pages.

**Spec**: [docs/specs/navigation-and-list-ux.md](../../../docs/specs/navigation-and-list-ux.md) (Status: Draft — approval gate `st-v059-nav-00`)

## Out of scope

- Per-row object-permission checks (denial stays server-side on open).
- Undo-after-delete / soft delete.
- Column visibility and density toggle.

## Stories (bottom-up)

| ID | Story | Size | Blocked by |
|---|---|---|---|
| st-v059-list-01 | [feat(views): per-user row target and delete permission in the list context](stories/featviews-per-user-row-target-and-delete-permission-in-the-l.md) | M | st-v059-nav-00 |
| st-v059-list-02 | [feat(templates): clickable list rows and Edit/Delete on detail and edit pages](stories/feattemplates-clickable-list-rows-and-edit-delete-on-detail.md) | M | st-v059-list-01 |
| st-v059-list-03 | [feat(templates): red icon delete with a shared confirm dialog](stories/feattemplates-red-icon-delete-with-a-shared-confirm-dialog.md) | M | st-v059-list-02 |

## Parent

- Milestone: `v059-navigation-list-ux` (v0.5.9 — Navigation & List UX)

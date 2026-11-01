---
type: epic
id: ep-v059-nav-01
title: "epic(nav): grouped sidebar, pinned models and command palette"
status: backlog
priority: high
owner: null
labels:
  - planned
  - area:core
  - area:templates
  - frontend
  - backend
  - size:L
milestone_ref:
  id: v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Overview

Make the admin navigable at 20–60 models: domain groups with icons (`nav_group`, `nav_order`, `icon`, `NavGroup`), collapsible groups and an icon rail, per-user pinned models stored server-side, and a Cmd/Ctrl+K palette over models, groups, plugin pages and recent items.

**Spec**: [docs/specs/navigation-and-list-ux.md](../../../docs/specs/navigation-and-list-ux.md) (Status: Draft — approval gate `st-v059-nav-00`)

## Out of scope

- Palette record search is a follow-up (`st-v059-nav-05`, needs an SDD addendum).
- Breadcrumbs and sidebar count badges.
- Drag-and-drop pin ordering.

## Stories (bottom-up)

| ID | Story | Size | Blocked by |
|---|---|---|---|
| st-v059-nav-00 | [review(spec): approve navigation and list UX SDD](stories/reviewspec-approve-navigation-and-list-ux-sdd.md) | S | — |
| st-v059-nav-01 | [feat(core): nav tree with NavGroup, nav_group/nav_order and a domain icon set](stories/featcore-nav-tree-with-navgroup-nav-group-nav-order-and-a-do.md) | M | st-v059-nav-00 |
| st-v059-nav-02 | [feat(templates): grouped collapsible sidebar with icon rail](stories/feattemplates-grouped-collapsible-sidebar-with-icon-rail.md) | M | st-v059-nav-01 |
| st-v059-nav-03 | [feat(nav): per-user pinned models in the sidebar](stories/featnav-per-user-pinned-models-in-the-sidebar.md) | L | st-v059-nav-02 |
| st-v059-nav-04 | [feat(nav): Cmd/Ctrl+K command palette with recent items and shortcut registry](stories/featnav-cmd-ctrl-k-command-palette-with-recent-items-and-sho.md) | M | st-v059-nav-01 |
| st-v059-nav-05 | [feat(nav): opt-in record search in the command palette](stories/featnav-opt-in-record-search-in-the-command-palette.md) | M | st-v059-nav-04 |

## Parent

- Milestone: `v059-navigation-list-ux` (v0.5.9 — Navigation & List UX)

---
type: epic
id: ep-v059-kbd-01
title: "epic(templates): form safety and keyboard navigation"
status: backlog
priority: medium
owner: null
labels:
  - planned
  - area:templates
  - frontend
  - size:M
milestone_ref:
  id: v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Overview

Stop people losing work (unsaved-changes guard, sticky save bar, Cmd/Ctrl+S) and let power users drive lists from the keyboard (`j`/`k`/Enter/`x`/`c`, `?` overlay) with an off switch for single-key shortcuts (WCAG 2.1.4). Builds on the shortcut registry from `st-v059-nav-04`.

**Spec**: [docs/specs/navigation-and-list-ux.md](../../../docs/specs/navigation-and-list-ux.md) (Status: Draft — approval gate `st-v059-nav-00`)

## Out of scope

- Shortcuts on non-list pages beyond Cmd/Ctrl+K and Cmd/Ctrl+S.

## Stories (bottom-up)

| ID | Story | Size | Blocked by |
|---|---|---|---|
| st-v059-kbd-01 | [feat(templates): unsaved-changes guard, sticky save bar and Cmd/Ctrl+S](stories/feattemplates-unsaved-changes-guard-sticky-save-bar-and-cmd.md) | M | st-v059-nav-04 |
| st-v059-kbd-02 | [feat(templates): list keyboard navigation and shortcuts overlay](stories/feattemplates-list-keyboard-navigation-and-shortcuts-overlay.md) | M | st-v059-nav-04, st-v059-list-02 |

## Parent

- Milestone: `v059-navigation-list-ux` (v0.5.9 — Navigation & List UX)

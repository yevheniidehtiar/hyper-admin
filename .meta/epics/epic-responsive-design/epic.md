---
type: epic
id: STHgdkjlft50
title: "epic(ui): Responsive Design — Mobile-First CSS Overhaul"
status: in_progress
priority: high
owner: null
labels:
  - size:L
  - planned
  - responsive
  - frontend
milestone_ref:
  id: lQHUqC1sVwjC
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T23:30:00Z
---

## Overview

Mobile-first responsive design overhaul for HyperAdmin. Transform the existing desktop-first CSS into a mobile-first architecture with breakpoint tokens, collapsible sidebar, stacked card tables, touch-friendly forms, and responsive navigation.

**Spec:** `docs/specs/responsive-design.md`
**Milestone:** v0.4.0 — Responsive Design (target: 2026-05-30)

## Demo Story

After all stories are complete, a user can open the HyperAdmin example app on a mobile device and:
1. See a clean single-column layout with a hamburger menu
2. Tap the hamburger to open a slide-in sidebar with model navigation
3. View list data as stacked cards with inline labels
4. Page through results with vertically stacked, touch-friendly pagination
5. Fill out create/edit forms with finger-friendly inputs
6. See the login, detail, and dashboard views all properly adapted

## Tracks

### Track 1: CSS Foundation (Critical Path)
- `chore(pm): rename milestone #15 and create responsive SDD` (#447) — DONE
- `refactor(ui): mobile-first CSS architecture with breakpoint tokens` (#452) — READY (blocker #447 done)

### Track 2: Component Responsive Behavior
- `feat(ui): collapsible sidebar with hamburger menu toggle` (#458) — blocked_by #452
- `feat(ui): responsive data table with stacked card layout` (#461) — blocked_by #452
- `feat(ui): create dashboard template with widget cards` (#463) — blocked_by #462
- `feat(ui): mobile-optimized pagination and filter bar` (#464) — blocked_by #461
- `feat(ui): responsive navbar with mobile optimizations` (#465) — blocked_by #458

### Track 3: View-Level Polish
- `feat(ui): touch-friendly forms and inline formsets on mobile` (#467) — blocked_by #452
- `feat(ui): responsive login, detail, and dashboard views` (#470) — blocked_by #458, #461, #464, #465, #467

### Track 4: Validation & Docs
- `test(e2e): responsive design viewport and interaction tests` (#471) — blocked_by all Track 2+3
- `docs: responsive design guide and breakpoint reference` (#472) — blocked_by #452, #470 (priority: low, deferrable)

## Critical Path

```
#447 (done) → #452 (CSS foundation) → #458 (sidebar) → #465 (navbar) ─┐
                                     → #461 (table)   → #464 (pagination)─┤
                                     → #467 (forms) ──────────────────────┤
                                                                          ├→ #470 → #471 (E2E)
```

## Scope Notes

**Core v0.4.0 (must-ship):** #452, #458, #461, #464, #465, #467, #470, #471
**Deferrable (priority: low):** #463 (dashboard template — blocked by external #462), #472 (docs)

The dashboard template (#463) depends on the dashboard builder epic (#462) which is external to this epic. If #462 is not ready by milestone target, #463 can ship in a follow-up without blocking the responsive demo.

## Acceptance Criteria

- [ ] Mobile-first CSS with breakpoint tokens
- [ ] Collapsible sidebar with hamburger toggle
- [ ] Data tables as stacked cards on mobile
- [ ] Touch-friendly forms and pagination
- [ ] Responsive navbar, login, detail, and dashboard views
- [ ] Comprehensive E2E viewport tests
- [ ] (low) Dashboard widget cards responsive grid
- [ ] (low) Developer documentation for responsive system

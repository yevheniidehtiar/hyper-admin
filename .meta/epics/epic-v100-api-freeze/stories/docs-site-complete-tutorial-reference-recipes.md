---
type: story
id: st-v100-freeze-04
title: "docs: docs site complete — tutorial, existing-app guide, reference, recipes"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - size:M
  - planned
  - area:docs
estimate: null
epic_ref:
  id: ep-v100-freeze-01
created_at: 2026-11-20T00:00:00Z
updated_at: 2026-11-20T00:00:00Z
---

## Summary

Close the gaps in the docs site before 1.0: every shipped feature has a guide or a recipe, the tutorial and
the existing-app guide run as written against `develop`, and the reference covers the public API.

## Files to Change

- **Modified / New:** pages under `docs/` found missing by the audit
- **Modified:** `zensical.toml` (nav entries)

## Acceptance Criteria

- [ ] A feature-to-page table shows a guide or recipe for every item under "What's shipped" in `docs/roadmap.md`
- [ ] The tutorial and the existing-app guide were followed start to finish on a clean checkout
- [ ] No internal 404s; `poe docs:build` passes

## Blocked by

- `test-public-api-audit-and-drift-guard` (st-v100-freeze-03)
- `docs-migration-guides-django-sqladmin-flask-admin` (st-v100-freeze-02)

## Parent

- Epic: `epic-v100-api-freeze` (v1.0 — Stable Release)

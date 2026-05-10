---
type: epic
id: ups-readiness-01
title: "epic(meta): Upstream Readiness — H2/H3/H4/H5/H6/H12/H13/H14/H15/H20"
status: todo
priority: high
owner: null
labels:
  - tracking
  - planned
  - upstream-readiness
milestone_ref: null
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Overview

Umbrella tracking epic for the ten generic admin capabilities (H2–H20) HyperAdmin
must ship before it can serve as the framework backbone for any consumer admin
application. Each capability is delivered through its own milestone via the
project's standard pipeline (`.claude/rules/bdd-conventions.md`,
`sdd-conventions.md`, `planning-playbook.md`). This epic is metadata-only: it
holds no implementation work itself.

The H-list is intentionally framework-neutral. No consumer-specific naming,
schema, or business logic enters this repository. See
`docs/specs/upstream-readiness-plan.md` (this epic body) for the qualification
matrix.

## Capability Index

| H#  | Capability                          | Status          | Milestone                              |
|-----|-------------------------------------|-----------------|----------------------------------------|
| H2  | Inline / nested forms               | shipped v0.5.0  | (polish patch — inline row errors)     |
| H3  | Bulk actions with param forms       | planned         | v0.5.5 — Bulk Actions & Autocomplete   |
| H4  | Detail-page panels / tabs           | planned         | v0.5.6 — Detail Panels & Filter Library|
| H5  | Object-level permissions            | shipped v0.5.1  | —                                      |
| H6  | HTMX FK/M2M autocomplete            | partial         | v0.5.5 — Bulk Actions & Autocomplete   |
| H12 | Filter library                      | planned         | v0.5.6 — Detail Panels & Filter Library|
| H13 | File / image upload (advanced)      | MVP shipped     | v0.3.2 — Advanced File Uploads         |
| H14 | OLAP / pivot reporting              | planned         | v0.5.4 — Reporting & Charts            |
| H15 | Chart components                    | planned         | v0.5.4 — Reporting & Charts            |
| H20 | Tabular permission-matrix UI        | planned         | v0.5.7 — Permissions Matrix            |

## Sequencing

1. **v0.5.0 follow-up** — H2 inline-row error highlighting (bugfix patch).
2. **v0.5.5** — H3 bulk actions and H6 autocomplete (unblocks consumer build).
3. **v0.5.6** — H4 detail panels and H12 filter library (depends on H6 wiring).
4. **v0.5.4** — H14 OLAP reporting and H15 charts (depends on H12 filter forms).
5. **v0.3.2** — H13 advanced uploads (independent track, in_progress).
6. **v0.5.7** — H20 permission matrix (depends on H5 surface area).

## SDDs Required

| Milestone | New SDDs |
|-----------|----------|
| v0.3.2    | `docs/specs/file-uploads-advanced.md` |
| v0.5.5    | `docs/specs/bulk-actions.md`, `docs/specs/htmx-autocomplete.md` |
| v0.5.6    | `docs/specs/detail-panels.md`, `docs/specs/filter-library.md` |
| v0.5.4    | `docs/specs/olap-reporting.md`, `docs/specs/chart-components.md` |
| v0.5.7    | `docs/specs/permission-matrix-ui.md` |

Existing SDDs reused: `file-uploads-mvp.md`, `object-permissions-mfa.md`.

## Acceptance (qualification suite)

The ten readiness checks run against `examples/full-demo/` (new in v0.5.7) using
framework-generic domain models (`Order`, `Invoice`, `Product`, `Supplier`).
When every check passes on `develop`, HyperAdmin is upstream-ready:

- [ ] H2 polish — nested formset save with one failing child highlights that row
- [ ] H3 — bulk action across 5 rows, 1 fails, per-row outcome page rendered
- [ ] H4 — detail page exposes Invoice/History/Transitions panels (panel registry + PDF demo)
- [ ] H5 — list view filterable by current user via `IsOwnerFilter`
- [ ] H6 — FK autocomplete narrows variants by selected supplier, "+" creates inline
- [ ] H12 — sidebar applies date-range + multi-FK + boolean over HTMX, saved as named view
- [ ] H13 — JPEG upload renders thumbnail in list
- [ ] H14 — OLAP report sales-by-SKU × month with quarter bucketing, CSV+XLSX export
- [ ] H15 — same dataset charted via SVG/Chart.js widget
- [ ] H20 — permission matrix flips view-but-not-edit for a role, detail page reflects it

## Out of Scope

- Anything tied to a specific downstream app — domain models, integration adapters, app-specific business rules.
- Framework features outside the H-list (state-machine field, audit trail, polymorphic models, money fields, document numbering) — these stay at the consumer layer.

## Parent

- Roadmap: project-wide tracking

## Children (stories)

See `stories/` for per-H# tracker entries.

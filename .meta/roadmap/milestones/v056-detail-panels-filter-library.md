---
type: milestone
id: v056-dpfl-01
title: v0.5.6 — Detail Panels & Filter Library
status: planned
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

H4 + H12 from upstream readiness. Declarative `panels` registry on
`AdminOptions` with a tabbed detail layout supporting `HTMLResponse` /
`StreamingResponse` per panel (PDF-streaming demo included). New
`src/hyperadmin/filters/` module with `DateRangeFilter`, `MultiFKFilter`,
`MultiChoiceFilter`, `BooleanFilter`, `IsOwnerFilter`, `CurrentPeriodDefault`,
plus URL-shareable querystring state, HTMX partial reload of the filtered
list, and per-user named saved views (table `hyperadmin_saved_view`).

Scope decision recorded in the H4 SDD: HyperAdmin ships the panel registry,
tabbed detail layout, and a PDF-streaming demo panel. History/Transitions
panel *content* remains an extension point exercised by downstream apps.

Spec: `docs/specs/detail-panels.md`, `docs/specs/filter-library.md`.
Tracking: `.meta/epics/epic-upstream-readiness/` (H4, H12).

---
type: milestone
id: 8DidH5NiN6cP
title: v0.5.4 — Reporting & Charts
status: in_progress
github:
  milestone_id: 22
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3ba2173be78db3e6aff2215a420cdcbde415e8c1df238076ede716c87e2712ed
  synced_at: 2026-04-07T17:23:23.788Z
created_at: 2026-04-02T13:44:25Z
updated_at: 2026-05-11T00:00:00Z
---

H14 + H15 from upstream readiness — re-scoped from "Dashboard Builder" to
match the framework-neutral capability vocabulary. New
`src/hyperadmin/reports/` module: `ReportView`, declarative aggregates
(`Sum`, `Count`, `StringAggComma`, `Min`, `Max`, `Many2One`), crosstab
dimensions (one row group, N column groups), time-series bucketing
(day / week / month / quarter / year auto), filter-form integration via
H12, CSV / XLSX export, permission-aware via H5, cached materialisation
hook so a fact table can back a `ReportView`. SVG bar/line/stacked-bar/pie
components and an HTMX-loaded Chart.js widget bound to a `ReportView`
dataset.

Spec: `docs/specs/olap-reporting.md`, `docs/specs/chart-components.md`.
Tracking: `.meta/epics/epic-upstream-readiness/` (H14, H15).

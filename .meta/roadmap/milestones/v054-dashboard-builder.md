---
type: milestone
id: 8DidH5NiN6cP
title: v0.5.4 — Reporting & Charts
status: in_progress
created_at: 2026-04-02T13:44:25Z
updated_at: 2026-10-18T00:00:00Z
---

**Roadmap position 9/16 (2026-09-28 re-cut).** Reporting (H14) and charts (H15). The original Dashboard Builder epic (#422) is linked here as the widget/layout layer over `ReportView` — kept, not cut.

H14 + H15 from upstream readiness — re-scoped from "Dashboard Builder" to
match the framework-neutral capability vocabulary. New
`plugins/hyperadmin-reports/src/hyperadmin_reports/` module: `ReportView`, declarative aggregates
(`Sum`, `Count`, `StringAggComma`, `Min`, `Max`, `Many2One`), crosstab
dimensions (one row group, N column groups), time-series bucketing
(day / week / month / quarter / year auto), filter-form integration via
H12, CSV / XLSX export, permission-aware via H5, cached materialisation
hook so a fact table can back a `ReportView`. SVG bar/line/stacked-bar/pie
components and an HTMX-loaded Chart.js widget bound to a `ReportView`
dataset.

Spec: `docs/specs/olap-reporting.md`, `docs/specs/chart-components.md`.
Tracking: `.meta/epics/epic-upstream-readiness/` (H14, H15).

**Roadmap change (2026-10-18): reports + charts → plugin.** `ReportView`, the aggregates and
the chart components no longer go into core `src/hyperadmin/reports/`; they ship as the
first-party plugin **`hyperadmin-reports`** (in-repo uv workspace member
`plugins/hyperadmin-reports/`, published to PyPI separately), built on the plugin UI seams
from `docs/specs/plugin-registry.md` (phase 1). This milestone therefore depends on plugin
registry phases 1a/1b.

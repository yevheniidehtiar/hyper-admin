---
type: epic
id: ep-v054-olap-01
title: "epic(reports): OLAP / pivot reporting with CSV+XLSX export"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - backend
  - upstream-readiness
  - H14
milestone_ref:
  id: 8DidH5NiN6cP
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Overview

Implements upstream readiness capability **H14**: new
`src/hyperadmin/reports/` package with declarative aggregates, crosstab
dimensions, time-series bucketing, filter integration (via H12), CSV / XLSX
export, permission gating (via H5), and a cached materialisation seam for
fact-table-backed reports.

**SDD:** [`docs/specs/olap-reporting.md`](../../../docs/specs/olap-reporting.md)
(required — new top-level module, multi-module integration).

## Tracks

### Track A: Aggregates + crosstab core
- `reports/aggregates.py` — `Sum`, `Count`, `Min`, `Max`, `StringAggComma`, `Many2One`.
- `reports/view.py` — `ReportView` base + registration.
- `reports/crosstab.py` — pivot builder.
- `reports/bucketing.py` — `TimeBucket` + `auto`-period resolver.

### Track B: Source dispatch + filter wiring
- `reports/cache.py` — `FactTableSource` seam.
- Filter integration with `filters/` from v0.5.6.
- Source-selection dispatcher: live query vs fact-table.

### Track C: Export endpoints + routes
- CSV streamer with proper content-disposition.
- XLSX streamer using `openpyxl.write_only` (memory-safe).
- Permission codename `view_report_{slug}` enforcement.
- Three routes per registered `ReportView`.

### Track D: Templates + unit/E2E
- `templates/reports/list.html`, `detail.html`.
- Export buttons + filter sidebar reuse.
- E2E for the eight SDD scenarios.

## Scenarios

See SDD `## BDD Scenarios` (eight scenarios: registration, single-group sum,
crosstab, auto-bucketing, CSV export, XLSX export, permission gating, fact-
table cache).

## Acceptance Criteria

- [ ] `reports/` package with documented public API
- [ ] Six aggregates implemented + unit tested
- [ ] Pivot builder produces correct grids across dialects
- [ ] Time-bucketing including `auto` resolver
- [ ] Filter integration via `filters/` (v0.5.6)
- [ ] CSV + XLSX export streamed (no in-memory blowup)
- [ ] `FactTableSource` swaps the live query transparently
- [ ] Permission codename gates report access
- [ ] Eight SDD scenarios pass
- [ ] `poe lint` and `poe test` pass

## Blocked by

- `reviewspec-approve-sdd-olap-reporting`
- Epic `epic-v056-filter-library` (depends on `FilterDef` protocol)

## Parent

- Milestone: `v054-dashboard-builder` (Reporting & Charts)
- Tracking: `epic-upstream-readiness` (H14)

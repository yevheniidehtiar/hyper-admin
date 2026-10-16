---
type: story
id: st-v054-charts-00
title: "review(spec): approve SDD for chart components"
status: done
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - upstream-readiness
  - H15
estimate: null
epic_ref:
  id: ep-v054-charts-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-10-17T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/chart-components.md` before
implementation sub-tasks may start.

## Checklist

- [x] SVG primitives cover H15 acceptance — line, bar, stacked bar, sparkline + frame
      (pie dropped: not in the design system)
- [x] ~~Default mode `svg`, opt-in `chartjs`~~ — superseded: SVG only, no Chart.js (owner decision)
- [x] ~~Vendored Chart.js (no CDN)~~ — superseded: no Chart.js at all
- [x] Accessibility: data-table fallback on by default
- [x] Charts placed under `widgets/` (not `reports/`) — boundary acceptable
- [x] Open Questions resolved (see the SDD Decision Log)

## Resolution (2026-10-17)

1. Vendor Chart.js or load from CDN? → neither; no Chart.js. Charts are server-rendered SVG built
   from `docs/design/system/components/Chart/`, and the design system wins over the SDD.
2. CSS variable palette names? → the design-system tokens `--ha-chart-1` … `--ha-chart-6`,
   `--ha-chart-grid`, `--ha-chart-axis`.
3. Data-table fallback default? → on by default ("Show as table" `<details>` after every chart).

## Parent

- Epic: `epic-v054-chart-components`

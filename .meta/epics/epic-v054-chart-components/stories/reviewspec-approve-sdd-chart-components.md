---
type: story
id: st-v054-charts-00
title: "review(spec): approve SDD for chart components"
status: todo
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
updated_at: 2026-05-11T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/chart-components.md` before
implementation sub-tasks may start.

## Checklist

- [ ] Four SVG primitives cover H15 acceptance
- [ ] Default mode `svg`, opt-in `chartjs` — correct
- [ ] Vendored Chart.js (no CDN) — confirmed acceptable
- [ ] Accessibility: data-table fallback on by default
- [ ] Charts placed under `widgets/` (not `reports/`) — boundary acceptable
- [ ] Open Questions resolved (CDN vs vendor, CSS variables, fallback default)

## Open Questions to resolve

1. Vendor Chart.js or load from CDN?
2. CSS variable palette names — `--ha-chart-N`?
3. Data-table fallback default on or opt-in?

## Parent

- Epic: `epic-v054-chart-components`

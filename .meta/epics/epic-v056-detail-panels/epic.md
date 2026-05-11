---
type: epic
id: ep-v056-dp-01
title: "epic(detail): tabbed detail panels with HTMX lazy-load and PDF streaming"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - backend
  - frontend
  - upstream-readiness
  - H4
milestone_ref:
  id: v056-dpfl-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Overview

Implements upstream readiness capability **H4**: `panels` registry on
`AdminOptions`, `@panel` decorator, tabbed detail layout with HTMX lazy-load,
and a bundled `PDFStreamPanel` demo. History/Transitions panel content is an
extension point for downstream apps — out of scope here per the H4 SDD.

**SDD:** [`docs/specs/detail-panels.md`](../../../docs/specs/detail-panels.md)
(required — touches `core/`, `views/`, templates).

## Tracks

### Track A: Registry + decorator (core)
- `src/hyperadmin/core/panels.py` — `PanelDef`, `@panel` decorator, `collect_panels`.
- `AdminOptions.panels: list[PanelDef] | None`.
- Slug-collision validation at registration.
- Default permission codename derivation (`view_{model}_panel_{slug}`).

### Track B: View routes + streaming (views)
- `DynamicModelView.render_panel_view` — `GET /{model}/{id}/panels/{slug}`.
- `DynamicModelView.stream_panel_view` — `GET /{model}/{id}/panels/{slug}/stream`.
- StreamingResponse detection → iframe wrapper fragment.
- Per-panel permission re-check.
- Bundled `hyperadmin.panels.pdf_stream_panel` factory.

### Track C: Templates + E2E (frontend)
- `templates/detail.html` — tab strip slot under `{% if panels %}`.
- `templates/components/panel_tab_strip.html`.
- `data-testid` exports: `panel-tab-{slug}`, `panel-body-{slug}`, `panel-iframe-{slug}`.
- E2E suite covering all six scenarios in the SDD.

## Scenarios

See SDD `## BDD Scenarios` (six scenarios: tab render, lazy-load, streaming,
forbidden, slug collision, permission gate).

## Acceptance Criteria

- [ ] `PanelDef` + `@panel` defined and unit tested
- [ ] `AdminOptions.panels` validated for slug uniqueness at registration
- [ ] Two new routes registered per panel-bearing model
- [ ] Streaming handlers yield `<iframe>` wrapper; HTML handlers swap inline
- [ ] Permission codename gates every panel request (default + override)
- [ ] `PDFStreamPanel` factory in `hyperadmin.panels` package
- [ ] `detail.html` backward compatible when `panels` is None
- [ ] Six E2E scenarios pass
- [ ] `poe lint` and `poe test` pass

## Blocked by

- `reviewspec-approve-sdd-detail-panels`

## Parent

- Milestone: `v056-detail-panels-filter-library`
- Tracking: `epic-upstream-readiness` (H4)

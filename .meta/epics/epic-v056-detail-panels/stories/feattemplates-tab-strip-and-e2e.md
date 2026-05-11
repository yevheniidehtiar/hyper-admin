---
type: story
id: st-v056-dp-03
title: "feat(templates+e2e): tab strip and panel E2E coverage"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - frontend
  - tests
  - upstream-readiness
  - H4
estimate: null
epic_ref:
  id: ep-v056-dp-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Render the tab strip in `detail.html` under `{% if panels %}` and add a
component partial. Each tab carries `hx-get` for lazy load. Cover all six
SDD scenarios in Playwright.

**Spec:** [`docs/specs/detail-panels.md`](../../../../docs/specs/detail-panels.md)

## Files to Change

- **Modified:** `src/hyperadmin/templates/detail.html` — tab strip slot
- **New:** `src/hyperadmin/templates/components/panel_tab_strip.html`
- **New:** `tests/e2e/test_detail_panels.py`
- **New:** `tests/_fixtures/sample.pdf` — small PDF used by PDFStreamPanel demo

## data-testid Reference

| Element | testid |
|---|---|
| Tab strip container | `panel-tabs` |
| Single tab link | `panel-tab-{slug}` |
| Active panel body | `panel-body-{slug}` |
| Streaming-mode iframe | `panel-iframe-{slug}` |

## Scenarios → Tests

| Scenario | Test function |
|---|---|
| detail page renders configured panel tabs | `test_detail_page_renders_configured_panel_tabs` |
| panel body lazy-loads when its tab becomes visible | `test_panel_body_lazy_loads_on_tab_click` |
| streaming panel returns Content-Disposition inline | `test_streaming_panel_serves_inline_pdf` |
| panel handler raising HTTPException(403) surfaces forbidden | `test_panel_handler_403_surfaces_forbidden_body` |
| panel slug collision raises at registration | `test_panel_slug_collision_raises_at_registration` (unit) |
| permission codename gates panel access | `test_permission_codename_gates_panel_access` |

## Acceptance Criteria

- [ ] Tab strip rendered only when `panels` configured
- [ ] Each tab has the `data-testid` per the table above
- [ ] PDF fixture in `tests/_fixtures/sample.pdf`
- [ ] All six scenarios covered (slug-collision as unit test, others E2E)
- [ ] Visual snapshot baseline updated
- [ ] `poe test:e2e -k detail_panels` passes

## Blocked by

- `featviews-panel-render-and-stream`

## Parent

- Epic: `epic-v056-detail-panels`

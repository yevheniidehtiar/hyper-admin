---
type: story
id: st-v056-dp-02
title: "feat(views): render_panel_view + stream_panel_view + PDFStreamPanel factory"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - backend
  - upstream-readiness
  - H4
estimate: null
epic_ref:
  id: ep-v056-dp-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Register the two panel routes per panel-bearing model. `render_panel_view`
inspects the handler's return type: `HTMLResponse` is swapped inline,
`StreamingResponse` is wrapped in an `<iframe>` whose `src` points to
`stream_panel_view`. Both routes re-check permission. Ship the bundled
`PDFStreamPanel` factory in `hyperadmin.panels`.

**Spec:** [`docs/specs/detail-panels.md`](../../../../docs/specs/detail-panels.md)

## Files to Change

- **Modified:** `src/hyperadmin/views/dynamic.py` — add both panel views, register routes
- **New:** `src/hyperadmin/panels/__init__.py` — re-exports
- **New:** `src/hyperadmin/panels/pdf.py` — `pdf_stream_panel` factory
- **Modified:** `tests/unit/test_dynamic_views.py` — panel-view tests

## Scenarios

```
Scenario: render_panel_view returns 404 for unknown slug
  When  GET /admin/orders/1/panels/missing
  Then  response is 404 with detail "Unknown panel"

Scenario: HTMLResponse handler returns fragment inline
  Given a panel handler returning HTMLResponse(content="<p>ok</p>")
  When  GET /admin/orders/1/panels/x
  Then  response body is "<p>ok</p>" and content-type is text/html

Scenario: StreamingResponse handler returns iframe wrapper
  Given a panel handler returning a StreamingResponse
  When  GET /admin/orders/1/panels/x
  Then  response body contains "<iframe" with src ending in "/panels/x/stream"

Scenario: stream_panel_view streams the bytes with inline disposition
  Given the same handler
  When  GET /admin/orders/1/panels/x/stream
  Then  response Content-Disposition is "inline"
  And   body bytes equal the handler's stream

Scenario: permission codename gates panel access
  Given user lacks "view_order_panel_invoice"
  When  GET /admin/orders/1/panels/invoice
  Then  response is 403
```

## Acceptance Criteria

- [ ] `render_panel_view` and `stream_panel_view` registered
- [ ] StreamingResponse detection wraps in iframe with correct `src`
- [ ] HTMLResponse swapped inline
- [ ] Per-panel permission enforced; default codename applied when override absent
- [ ] `pdf_stream_panel` factory in `hyperadmin.panels` returns a `PanelDef`
- [ ] 5 scenarios pass at unit-test level
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-add-panel-registry`

## Parent

- Epic: `epic-v056-detail-panels`

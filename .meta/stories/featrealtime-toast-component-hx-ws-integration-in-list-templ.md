---
type: story
id: YhAU7COff6_D
title: "feat(realtime): Toast component + hx-ws integration in list templates"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:frontend
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 312
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b8eb681bd7817e9bcc80b39d216dbcc40ded0edc3a69c4efef3d18ae78773fb4
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:59:15Z
updated_at: 2026-03-29T06:59:15Z
---

## Context
The final assembly step for notifications: connect the WebSocket infrastructure to the browser via HTMX hx-ws, and render live row updates and toast notifications.

## Acceptance Criteria
- [ ] `src/hyperadmin/templates/components/toast.html` created (auto-dismiss after 4s, accessible via `role=alert` + `aria-live=polite`)
- [ ] `_base.html` loads `htmx-ws.js` extension
- [ ] `list.html` adds `hx-ext="ws"` `ws-connect="/admin/ws?channel=admin:{model_name}"` on the list container
- [ ] `ConnectionManager` renders row HTML fragment via Jinja2 and pushes as `hx-swap-oob="outerHTML:#row-{pk}"` on update events
- [ ] On `deleted` events: sends `<tr id="row-{pk}" hx-swap-oob="delete"></tr>`
- [ ] On `created` events: sends toast notification
- [ ] T6 and T10 must be merged first

## Files Likely Affected
- `src/hyperadmin/templates/components/toast.html` (new)
- `src/hyperadmin/templates/_base.html`
- `src/hyperadmin/templates/list.html`
- `src/hyperadmin/views/websocket.py`

## Dependencies
Depends on: #307, #311

## Notes for Implementer
Use `hx-swap-oob` for out-of-band swaps. The ConnectionManager needs access to the Jinja2 template environment to render fragments — inject it from `Admin`. Toast must not break pages where WS is unavailable (graceful degradation).

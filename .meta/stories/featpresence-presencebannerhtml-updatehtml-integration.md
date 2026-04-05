---
type: story
id: vEm8VOQ2LfUX
title: "feat(presence): presence_banner.html + update.html integration"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:frontend
  - area:presence
estimate: null
epic_ref: null
github:
  issue_number: 328
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5033bc3ee57116e30b19b89df3d8604cd56d7110c0b2922fe261406e754fb606
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T07:01:49Z
updated_at: 2026-03-29T07:01:49Z
---

## Context
The presence banner is the user-facing indicator on edit forms showing who else is currently viewing or editing the record. Uses Alpine.js for the client-side heartbeat sender.

## Acceptance Criteria
- [ ] `src/hyperadmin/templates/components/presence_banner.html` created
- [ ] Shows list of users with display name, mode (viewing/editing), and relative time
- [ ] Empty state: banner hidden when no other users present
- [ ] Banner injected in `update.html` above the form with `id="presence-banner"` as `hx-swap-oob` target
- [ ] Client-side heartbeat: Alpine.js snippet sends `{action: "editing", model, pk, user}` over WS every 8s
- [ ] Degrades gracefully when WS unavailable (no JS error, no broken layout)

## Files Likely Affected
- `src/hyperadmin/templates/components/presence_banner.html` (new)
- `src/hyperadmin/templates/update.html`

## Dependencies
Depends on: #327

## Notes for Implementer
Alpine.js is already used in the project (`components/fieldset.html`). Use `x-data` + `x-init` for the heartbeat interval. Access current user from template context (already available via auth middleware).

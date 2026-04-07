---
type: story
id: uKSG-lCQo2tp
title: "feat(ui): enhance drag-and-drop with visual feedback and keyboard shortcuts"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:templates
  - size:M
  - area:frontend
estimate: null
epic_ref:
  id: tIHHxFEv8ZzJ
github:
  issue_number: 405
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d0bdfd4c5057cae3e41d3c6eb1f14fd52b598e655b7f994915f57e0aa06d4c76
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:16:50Z
updated_at: 2026-03-31T21:16:50Z
---

## Context

Polishes the drag-and-drop zone from issue #403 with visual state transitions, clipboard paste support, and multi-file rejection for single-file fields.

**Depends on**: #403

## Scenarios

**Scenario: drag-over changes visual state**
  Given the drag-drop zone is visible
  When  a file is dragged over the zone
  Then  the zone border changes to highlight color
  And   the label changes to "Release to upload"

**Scenario: drag-leave resets visual state**
  Given a file is being dragged over the zone
  When  the file is dragged away without releasing
  Then  the zone returns to its default visual state

**Scenario: clipboard paste triggers upload**
  Given the drag-drop zone or page is focused
  When  the user pastes an image from clipboard (Ctrl+V)
  Then  the pasted image is processed as if it were a dropped file

**Scenario: multiple files rejected for single-file fields**
  Given a single-file `ImageType` field
  When  the user drops 3 files simultaneously
  Then  only the first file is processed
  And   a non-blocking warning "Only one file allowed" is shown

## Acceptance Criteria

- [ ] CSS transitions for drag-over / drag-leave states in `static/css/` or inline Alpine.js `:class` bindings
- [ ] `dragover` → highlight border + text change; `dragleave` → reset
- [ ] Clipboard `paste` event on the zone processes `event.clipboardData.files[0]`
- [ ] Multi-file drop: take `files[0]`, show warning, discard others
- [ ] No external JS dependencies — Alpine.js only

## Files Likely Affected

- `src/hyperadmin/templates/widgets/image_preview_input.html`
- `src/hyperadmin/static/css/hyperadmin.css` (or new `uploads.css`)

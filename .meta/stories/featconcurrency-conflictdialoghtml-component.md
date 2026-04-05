---
type: story
id: A4MEazuVD0dG
title: "feat(concurrency): conflict_dialog.html component"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:S
  - area:frontend
  - area:concurrency
estimate: null
epic_ref: null
github:
  issue_number: 320
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:038888cb7325f125e8b09e608be933fc4caab4c15971291e59bb90ced5b5544a
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T07:00:31Z
updated_at: 2026-03-29T07:00:31Z
---

## Context
The conflict dialog is the user-facing resolution UI when a concurrent edit collision is detected. It must be clear, actionable, and accessible.

## Acceptance Criteria
- [ ] `src/hyperadmin/templates/components/conflict_dialog.html` created
- [ ] Uses `role="alertdialog"` for accessibility
- [ ] Message: "This record was modified since you opened it."
- [ ] **Reload** button: `hx-get` to `update_form_view` URL, `hx-target="#model-form-body"` — fetches fresh form
- [ ] **Save Anyway** button: resubmits current form data with `__force=true` hidden field
- [ ] Styled using existing `ha-*` CSS design tokens (no new CSS classes)

## Files Likely Affected
- `src/hyperadmin/templates/components/conflict_dialog.html` (new)

## Dependencies
Depends on: #319

## Notes for Implementer
The dialog replaces the form body on conflict — it is not a modal overlay. Keep it simple: two buttons, one message.

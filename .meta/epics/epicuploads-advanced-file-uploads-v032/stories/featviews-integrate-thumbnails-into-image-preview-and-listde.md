---
type: story
id: qgi3H0Wq3ZKV
title: "feat(views): integrate thumbnails into image preview and list/detail views"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - area:templates
  - size:S
estimate: null
epic_ref:
  id: tIHHxFEv8ZzJ
github:
  issue_number: 409
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b7fb13c804703e0a5d242ae18822f2c31db5fca3a37263f224662e84a7777a69
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:17:42Z
updated_at: 2026-03-31T21:17:43Z
---

## Context

Uses the thumbnail generation helper (issue #404) to show small thumbnails in the list view and medium thumbnails in the detail/edit views, instead of full-size images.

**Depends on**: #403, #404

## Scenarios

**Scenario: list view shows 40x40 thumbnail for image column**
  Given a model with an `ImageType` column and a stored image
  When  the list view is rendered
  Then  a `40x40` thumbnail `<img>` is shown in the column (not the full-size image)

**Scenario: detail view shows 200x200 thumbnail with link to full image**
  Given a record with a stored image
  When  the detail view is rendered
  Then  a `200x200` thumbnail is shown
  And  clicking it opens the full-size image

## Acceptance Criteria

- [ ] List view: `generate_thumbnail(storage, filename, max_size=(40, 40))` called for `ImageType` columns
- [ ] Detail view: `generate_thumbnail(storage, filename, max_size=(200, 200))` with link to original
- [ ] Falls back to generic file icon if thumbnail generation fails
- [ ] Thumbnail `<img>` has `alt="{field_label}"` and `loading="lazy"` attributes

## Files Likely Affected

- `src/hyperadmin/views/dynamic.py` (enrich image fields with thumbnail URLs)
- `src/hyperadmin/templates/detail.html`
- `src/hyperadmin/templates/components/table.html`

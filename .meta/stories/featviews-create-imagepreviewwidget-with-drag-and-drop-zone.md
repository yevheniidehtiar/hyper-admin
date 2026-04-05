---
type: story
id: 8bhxDY_ynXBZ
title: "feat(views): create ImagePreviewWidget with drag-and-drop zone"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - area:templates
  - size:L
  - area:frontend
estimate: null
epic_ref: null
github:
  issue_number: 403
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5e787807ae030784b66e99bd42a394ed14f4c3e4820237b12e07bbbcb248c3b6
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-03-31T21:16:18Z
updated_at: 2026-03-31T21:16:19Z
---

## Context

Enhances `ImageType` fields with a rich drag-and-drop upload zone (using Alpine.js, consistent with the existing stack) and inline image preview using `URL.createObjectURL()` for instant client-side preview before upload.

**HTMX pattern**: Drag-and-drop handled by Alpine.js (`@dragover.prevent`, `@drop.prevent`). File upload uses the dedicated upload endpoint (issue #393) triggered via JavaScript `fetch()` or HTMX. Preview via `URL.createObjectURL()` (no server round-trip). Progress via `htmx:xhr:progress` event.

**Depends on**: v0.3.1 complete

## Scenarios

**Scenario: drag-drop zone renders for ImageType field**
  Given a model with an `ImageType` column `photo`
  When  the create form is rendered
  Then  a drag-drop zone with "Drop image here or click to select" text is displayed

**Scenario: file dropped on zone shows instant preview**
  Given the drag-drop zone is visible
  When  a user drops a valid image file on the zone
  Then  an inline image preview appears immediately (via `URL.createObjectURL()`)
  And   the hidden file input value is set

**Scenario: click on zone opens system file picker**
  Given the drag-drop zone is visible
  When  the user clicks the zone
  Then  the browser file picker opens filtered to image types

**Scenario: existing image shows preview in edit form**
  Given a record with `photo="product.jpg"`
  When  the edit form is rendered
  Then  the current image is shown as a preview thumbnail
  And   a "Remove" button is displayed

**Scenario: invalid file type dropped shows inline error**
  Given `allowed_types=["image/jpeg", "image/png"]`
  When  a user drops a `.txt` file
  Then  an error "File type not allowed" is shown inline in the drop zone

**Scenario: keyboard accessibility for drag-drop zone**
  Given the drag-drop zone is focused via keyboard
  When  the user presses Enter or Space
  Then  the file picker opens

## Acceptance Criteria

- [ ] `ImagePreviewWidget(FileInputWidget)` class in `views/forms.py`
- [ ] `templates/widgets/image_preview_input.html` — Alpine.js powered drag-drop zone
- [ ] `URL.createObjectURL()` used for instant preview (no server round-trip for preview)
- [ ] Hidden `<input type="file" hx-preserve>` receives the dropped/selected file
- [ ] "Remove" button triggers the file deletion endpoint (issue #394)
- [ ] `data-testid="image-drop-zone-{field_name}"` on the drop zone
- [ ] `aria-label`, `role="button"`, keyboard events (Enter/Space) for accessibility
- [ ] `_pick_widget()` returns `ImagePreviewWidget` for `FileFieldMeta(field_type="image")`

## Files Likely Affected

- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/templates/widgets/image_preview_input.html` (new)
- `tests/e2e/test_image_preview_widget.py` (new)

---
type: story
id: f5xkXG0OTfJv
title: "feat(adapters): clean up stored files when model record is deleted"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:adapters
  - size:M
  - area:uploads
estimate: null
epic_ref: null
github:
  issue_number: 395
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8d30639710da41d66a1dc37423760a2fe3277f417e7faabe2e9f25bfade88e16
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T21:13:42Z
updated_at: 2026-04-01T20:57:09Z
---

## Context

When a model record is deleted via the admin, any files associated with its file/image fields should be removed from storage to prevent orphaned files accumulating on disk.

**Spec**: `docs/specs/file-uploads.md`
**Depends on**: #388, #389

## Scenarios

**Scenario: file is removed from storage when record is deleted**
  Given a `Product` with `photo="product.jpg"` in local storage
  When  the `Product` is deleted via the admin delete action
  Then  `product.jpg` is removed from the storage backend

**Scenario: multiple file fields are all cleaned up**
  Given a `Product` with `photo="photo.jpg"` and `document="spec.pdf"`
  When  the `Product` is deleted
  Then  both `photo.jpg` and `spec.pdf` are removed from storage

**Scenario: missing file does not block record deletion**
  Given a `Product` with `photo="missing.jpg"` (file already gone from disk)
  When  the `Product` is deleted
  Then  the record is deleted successfully
  And   the missing file error is logged as a warning, not raised

## Acceptance Criteria

- [ ] `DynamicModelView.delete_action()` inspects the model for `FileType`/`ImageType` columns before calling `adapter.delete(pk)`
- [ ] Fetches the record first, collects file field values, calls `storage.delete()` for each non-None value
- [ ] Handles `FileNotFoundError` / `OSError` gracefully: logs warning, continues with record deletion
- [ ] Does NOT modify `BaseAdapter` — cleanup logic lives in the view layer
- [ ] Unit tests covering all three scenarios

## Files Likely Affected

- `src/hyperadmin/views/dynamic.py` (`delete_action` method)
- `tests/unit/test_file_cleanup.py` (new)

## Notes for Implementer

- Order: fetch record → delete files from storage → delete record from DB
- If storage cleanup fails, still delete the record (storage cleanup is best-effort)

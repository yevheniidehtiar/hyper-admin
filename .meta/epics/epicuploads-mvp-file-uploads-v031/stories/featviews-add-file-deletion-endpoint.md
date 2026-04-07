---
type: story
id: 1VL0MGPJdoLD
title: "feat(views): add file deletion endpoint"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - size:S
estimate: null
epic_ref:
  id: P6jeUKkioZJh
github:
  issue_number: 394
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7ce99a2cc794874f0807630b7c1af583200bf33561661c772c3d409569a64e1d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:13:28Z
updated_at: 2026-04-01T20:57:07Z
---

## Context

Allows removing a file from a record without deleting the record itself. Required for the "Remove file" button in edit forms.

**Spec**: `docs/specs/file-uploads.md`
**Depends on**: #388, #393

## Scenarios

**Scenario: delete endpoint removes file from storage and clears field**
  Given a `Product` with `document="report.pdf"` stored in local storage
  When  `DELETE /admin/product/{id}/file/document` is called
  Then  `report.pdf` is removed from the storage backend
  And   the `document` field on the record is set to `None`

**Scenario: deleting nonexistent file returns 404**
  Given a `Product` with `document=None`
  When  `DELETE /admin/product/{id}/file/document` is called
  Then  HTTP 404 is returned

## Acceptance Criteria

- [ ] New route `DELETE /{model_name}/{item_id}/file/{field_name}` in `routing.py`
- [ ] Fetches record via `adapter.get(item_id)`, checks `field_name` is a file field
- [ ] Calls `storage.delete(current_filename)` if file exists
- [ ] Updates record via `adapter.update(item_id, {field_name: None})`
- [ ] Returns HTTP 404 if field is already `None`
- [ ] Permission check via `_check_permission(request, "change")`
- [ ] HTMX response swaps out the file preview element

## Files Likely Affected

- `src/hyperadmin/views/dynamic.py` (new `delete_file_view` method)
- `src/hyperadmin/routing.py` (register new route)
- `tests/unit/test_delete_file_endpoint.py` (new)

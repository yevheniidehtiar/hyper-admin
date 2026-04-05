---
type: story
id: T0QmBO13cXfA
title: "feat(views): add dedicated file upload endpoint"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 393
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8f189c3dc7bf007309640c74e581a6e95110537e2d246e726d849c2dfc963f3f
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T21:13:15Z
updated_at: 2026-04-01T20:57:05Z
---

## Context

A dedicated `POST /{model}/upload` endpoint allows the UI to upload files asynchronously (separate from form submission). This enables future inline preview functionality and is required for the HTMX progress bar pattern (`htmx:xhr:progress` fires on the XHR upload).

**Spec**: `docs/specs/file-uploads.md`
**Depends on**: #388, #390

## Scenarios

**Scenario: upload endpoint accepts file and returns metadata**
  Given a model `Product` with a `FileType` column `document`
  When  `POST /admin/product/upload` with `field_name=document` and a valid file
  Then  the file is saved to storage
  And   the JSON response includes `{filename, url, size, content_type}`

**Scenario: upload endpoint rejects file failing validation**
  Given `max_size=1_000` bytes for the `document` field
  When  `POST /admin/product/upload` with a 5KB file
  Then  HTTP 422 is returned with a validation error message

**Scenario: upload endpoint requires authentication when auth is enabled**
  Given `auth_backend` is configured on the Admin
  When  an unauthenticated `POST /admin/product/upload`
  Then  HTTP 403 is returned

**Scenario: upload returns HTMX trigger header**
  Given the request includes `HX-Request: true`
  When  the file is uploaded successfully
  Then  the response includes `HX-Trigger: fileUploaded` header with the field name and URL

## Acceptance Criteria

- [ ] New route `POST /{model_name}/upload` registered in `src/hyperadmin/routing.py` alongside existing CRUD routes
- [ ] Endpoint accepts `multipart/form-data` with `file: UploadFile` and `field_name: str = Form(...)`
- [ ] Validates file using `uploads/validation.py` `validate_upload()`
- [ ] Saves via `self.storage`, returns `{"filename": ..., "url": ..., "size": ..., "content_type": ...}`
- [ ] Permission check via `_check_permission(request, "add")`
- [ ] `HX-Trigger` header set on success when `HX-Request` header is present
- [ ] Unit tests covering all four scenarios

## Files Likely Affected

- `src/hyperadmin/views/dynamic.py` (new `upload_view` method)
- `src/hyperadmin/routing.py` (register new route)
- `tests/unit/test_upload_endpoint.py` (new)

## Notes for Implementer

- Route name: `{model_name}-upload`
- The endpoint does NOT update the database — it only stores the file and returns metadata
- The stored filename/URL is then used by the form submission to set the model field value

---
type: story
id: UywHyt1Y2qUo
title: "feat(examples): add file upload fields to example apps"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:examples
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 400
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:cc000c359736a56f0743a57646b48bb737986de65ca3c8b5ed676f8a9b0a66c7
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-03-31T21:15:22Z
updated_at: 2026-04-01T20:57:18Z
---

## Context

The example apps (`examples/simple/` and/or `examples/erp/`) should demonstrate file upload functionality so users have a concrete working reference. Adds at least one `FileType` and one `ImageType` column to an existing example model.

**Depends on**: #392 (multipart form handling must be complete)

## Scenarios

**Scenario: simple example app includes a model with FileType and ImageType fields**
  Given the simple example app is running
  When  the user navigates to the admin
  Then  at least one model has a file upload field and one has an image upload field

**Scenario: file upload works end-to-end in the example app**
  Given the simple example app is running
  When  the user creates a record with a file attached
  Then  the file is stored in the local upload directory
  And   the detail view shows the download link

## Acceptance Criteria

- [ ] `examples/simple/models.py` — add `FileType` column (e.g. `document`) and `ImageType` column (e.g. `cover_image`) to an existing model (e.g. `Product`)
- [ ] `examples/simple/admin.py` — no changes needed if field auto-detection works; otherwise register the model
- [ ] `examples/simple/main.py` — ensure `Admin` is initialized without explicit `storage` param (tests defaults)
- [ ] `examples/erp/` (optional) — add `ImageType` column to `contacts/models.py` (e.g. avatar photo)
- [ ] Running `uv run uvicorn examples.simple.main:app --reload` shows the file upload widget in the admin

## Files Likely Affected

- `examples/simple/models.py`
- `examples/simple/admin.py` (if needed)
- `examples/erp/contacts/models.py` (optional)

## Notes for Implementer

- `fastapi-storages` must already be in `pyproject.toml` (it is — no new dependency)
- Use `FileSystemStorage(path="./uploads")` default (or let `Admin` use its default)
- Keep the model changes minimal — just add the two new columns

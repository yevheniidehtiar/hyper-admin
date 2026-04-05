---
type: epic
id: WseneZ8SMuds
title: "epic(uploads): MVP File Uploads -- v0.3.1"
status: done
priority: medium
owner: null
labels:
  - agent-task
  - area:uploads
milestone_ref:
  id: su9D95fALwEr
github:
  issue_number: 401
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b522db0ac972bea9c5a66448b4dd55c2eb9d9b623c249144b3945541e420db64
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-03-31T21:15:37Z
updated_at: 2026-04-04T17:48:19Z
---

## Overview

End-to-end file upload support for HyperAdmin using local file storage. Assembly-first: minimal working vertical slice with `<input type="file">`, multipart form handling, storage via `fastapi-storages`, and file display in CRUD views.

## Architecture

- New module: `src/hyperadmin/uploads/` (StorageBackend protocol, FileFieldMeta, validation)
- Extended: `core/fields.py` classify_field() → detects FileType/ImageType columns
- Extended: `views/forms.py` → FileInputWidget, has_file_fields, multipart extraction
- Extended: `views/dynamic.py` → upload/delete endpoints, file cleanup on record delete
- New template: `templates/widgets/file_input.html`
- HTMX pattern: `hx-encoding="multipart/form-data"` + `hx-preserve` for file inputs

## SDD

**Spec**: `docs/specs/file-uploads.md` (must be approved before implementation starts)

## Tasks

- [ ] #387 review(spec): approve SDD
- [ ] #388 feat(uploads): StorageBackend protocol + Admin wiring
- [ ] #389 feat(uploads): FileType/ImageType field detection
- [ ] #390 feat(uploads): file validation (allowed_types + max_size)
- [ ] #391 feat(views): FileInputWidget
- [ ] #392 feat(views): multipart/form-data + UploadFile handling
- [ ] #393 feat(views): dedicated upload endpoint
- [ ] #394 feat(views): file deletion endpoint
- [ ] #395 feat(adapters): file cleanup on record delete
- [ ] #396 feat(views): file fields in list/detail views
- [ ] #397 test(uploads): unit tests
- [ ] #398 test(e2e): E2E upload workflows
- [ ] #399 docs(uploads): usage guide + API reference
- [ ] #400 feat(examples): file upload in example apps

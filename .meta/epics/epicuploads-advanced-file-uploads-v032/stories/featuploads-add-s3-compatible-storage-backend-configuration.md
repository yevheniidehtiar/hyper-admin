---
type: story
id: B0PpsEj89D7_
title: "feat(uploads): add S3-compatible storage backend configuration"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:uploads
estimate: null
epic_ref:
  id: tIHHxFEv8ZzJ
github:
  issue_number: 402
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:205b4a78480b733ab09a38f0f55a4fcd70b06108cc027708a5cc892204ca81cb
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:15:56Z
updated_at: 2026-03-31T21:15:56Z
---

## Context

Extends the storage system with S3-compatible backends (AWS S3, Hetzner Object Storage, DigitalOcean Spaces, MinIO). Uses `fastapi_storages.S3Storage` which is already in the dependency tree. All file operations (save, delete, URL generation) work identically regardless of backend.

**Depends on**: v0.3.1 complete

## Scenarios

**Scenario: Admin accepts S3Storage instance**
  Given an `S3Storage` configured for DigitalOcean Spaces
  When  `Admin(app, engine=engine, storage=s3_storage)` is called
  Then  all file operations route through S3

**Scenario: S3 upload stores file and returns public URL**
  Given `S3Storage` with a configured bucket
  When  a file is uploaded via the admin create form
  Then  the file is stored in S3 and the detail view shows a public URL download link

**Scenario: S3 file deletion removes object from bucket**
  Given a record with a file stored in S3
  When  the file is deleted via the admin (delete endpoint or record deletion)
  Then  the S3 object is removed from the bucket

**Scenario: environment variables configure S3 storage**
  Given `HYPERADMIN_STORAGE_BACKEND=s3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME` are set
  When  `Admin(app, engine=engine)` is called without explicit `storage`
  Then  `admin.storage` is an `S3Storage` instance

## Acceptance Criteria

- [ ] `uploads/storage.py` provides `S3StorageBackend` wrapping `fastapi_storages.S3Storage`
- [ ] `HyperAdminSettings` gains optional S3 config fields: `storage_backend: Literal["local", "s3"] = "local"`, `aws_access_key_id`, `aws_secret_access_key`, `aws_s3_bucket_name`, `aws_s3_region`, `aws_s3_endpoint_url` (for compatible services)
- [ ] `Admin` default storage selection reads `settings.storage_backend` to choose `FileSystemStorage` vs `S3Storage`
- [ ] Documentation for Hetzner / DigitalOcean / AWS / MinIO configuration included
- [ ] Integration tests with mocked S3 (using `moto` or `pytest-mock`)

## Files Likely Affected

- `src/hyperadmin/uploads/storage.py`
- `src/hyperadmin/core/settings.py`
- `src/hyperadmin/core/app.py`
- `docs/user-guide/file-uploads.md` (S3 section)
- `tests/unit/test_s3_storage.py` (new)

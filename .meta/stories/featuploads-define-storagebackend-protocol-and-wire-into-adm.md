---
type: story
id: stwhfMBFqHDr
title: "feat(uploads): define StorageBackend protocol and wire into Admin"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:M
  - area:uploads
estimate: null
epic_ref: null
github:
  issue_number: 388
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:28286acff68dba52ea0a42a028661b07ce8db74ad18dd6ccd63e370a43f9a178
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T21:11:33Z
updated_at: 2026-04-03T09:30:46Z
---

## Context

HyperAdmin needs a storage abstraction for file uploads. `fastapi-storages>=0.1.0` is already declared in `pyproject.toml` — no new dependency needed. This issue wraps it with a HyperAdmin-native protocol and wires it into the `Admin` class so views can access the storage backend.

**Spec**: `docs/specs/file-uploads.md`

**Depends on**: #387 (SDD approval)

## Scenarios

**Scenario: Admin accepts explicit storage parameter**
  Given a FastAPI application
  When  `Admin(app, engine=engine, storage=FileSystemStorage(path="/tmp/uploads"))` is called
  Then  `admin.storage` is the provided `FileSystemStorage` instance

**Scenario: default storage is created from settings when none provided**
  Given `HYPERADMIN_UPLOAD_DIR` is set to `/var/uploads`
  When  `Admin(app, engine=engine)` is called without a `storage` argument
  Then  `admin.storage` is a `FileSystemStorage` with `path="/var/uploads"`

**Scenario: storage is accessible in DynamicModelView**
  Given `Admin` is mounted with a `FileSystemStorage`
  When  a `DynamicModelView` is created for any registered model
  Then  `view.storage` is the same storage instance

## Acceptance Criteria

- [ ] `src/hyperadmin/uploads/__init__.py` created — re-exports `StorageBackend` (opt-in import per CONSTITUTION)
- [ ] `src/hyperadmin/uploads/storage.py` defines `StorageBackend` protocol wrapping `fastapi_storages.base.BaseStorage`
- [ ] `HyperAdminSettings` in `core/settings.py` gains `upload_dir: str = "./uploads"` (env: `HYPERADMIN_UPLOAD_DIR`)
- [ ] `Admin.__init__` accepts optional `storage: StorageBackend | None` parameter; defaults to `FileSystemStorage(path=settings.upload_dir)`
- [ ] Upload directory is auto-created on startup
- [ ] Upload directory is served via `StaticFiles` mount (so stored files are accessible at `/static/uploads/...`)
- [ ] Storage is threaded through to `HyperAdminRouter` → `DynamicModelView`
- [ ] Unit tests with >90% coverage on new `uploads/` module

## Files Likely Affected

- `src/hyperadmin/uploads/__init__.py` (new)
- `src/hyperadmin/uploads/storage.py` (new)
- `src/hyperadmin/core/settings.py`
- `src/hyperadmin/core/app.py`
- `src/hyperadmin/routing.py`
- `src/hyperadmin/views/dynamic.py`
- `tests/unit/test_storage.py` (new)

## Notes for Implementer

- `fastapi_storages.filesystem.FileSystemStorage` is the concrete class to use for local storage
- Per CONSTITUTION: `uploads/` is a reserved Phase 3 domain — new module, not bolted onto existing files
- Do NOT import from `uploads/` inside `core/` — direction must be `views/ → core/ → uploads/` (no circular imports)
- The `uploads/__init__.py` must use lazy/opt-in imports so the package works without `fastapi-storages` installed

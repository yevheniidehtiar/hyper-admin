---
type: story
id: kcCYW-qTmGqI
title: "docs(uploads): file upload usage guide and API reference"
status: done
priority: medium
assignee: null
labels:
  - documentation
  - agent-task
  - area:docs
  - size:M
estimate: null
epic_ref:
  id: P6jeUKkioZJh
github:
  issue_number: 399
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:cc674ff9a46007f3868b0f50b3a25ea19f5295b540cf9b07b3a52d46e52ed35e
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:15:06Z
updated_at: 2026-04-01T20:57:16Z
---

## Context

Documentation for the file upload feature must ship with the MVP milestone so users can adopt it immediately. Covers getting started, field types, validation configuration, and local storage setup.

**Depends on**: All v0.3.1 feat issues (#388–#396)

## Scenarios

**Scenario: user can follow getting started guide to add FileType field**
  Given a developer reading `docs/user-guide/file-uploads.md`
  When  they follow the minimal example (model + Admin setup)
  Then  they have a working file upload in their admin

**Scenario: validation configuration is documented with examples**
  Given the file upload docs page
  When  the user looks for how to restrict file types and sizes
  Then  the `allowed_types` and `max_size` options are shown with concrete examples

**Scenario: docs page is reachable from the MkDocs navigation**
  Given `mkdocs.yml` is updated
  When  `poe docs:serve` is run
  Then  the file uploads page appears under User Guide in the nav

## Acceptance Criteria

- [ ] `docs/user-guide/file-uploads.md` created covering:
  - Minimal example: `FileType` column + `Admin` setup
  - Validation: `allowed_types=["image/jpeg", ".pdf"]`, `max_size=5_000_000`
  - Local storage configuration (`upload_dir` setting, `HYPERADMIN_UPLOAD_DIR` env var)
  - `FileType` vs `ImageType` differences
  - How files are served (StaticFiles mount)
  - Limitations: local storage only in MVP; S3 in v0.3.2
- [ ] `mkdocs.yml` updated to include the new page under "User Guide"
- [ ] No broken links in the docs (`poe docs:build` succeeds)

## Files Likely Affected

- `docs/user-guide/file-uploads.md` (new)
- `mkdocs.yml`

## Notes for Implementer

- Keep the getting started section short (< 20 lines of code)
- Link to `docs/specs/file-uploads.md` for the SDD (internal dev reference)
- Note that `fastapi-storages` must be installed: `uv add fastapi-storages`

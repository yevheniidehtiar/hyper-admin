---
type: story
id: jX5c3B_d0vGn
title: "feat(uploads): add file validation by allowed types list and max size"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:uploads
estimate: null
epic_ref:
  id: P6jeUKkioZJh
github:
  issue_number: 390
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:1c7c5112b193ffda630299e11dfe4e7747d5e727b256ec5b1dffe5b58f3a06f0
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:12:10Z
updated_at: 2026-04-01T20:56:59Z
---

## Context

File uploads must be validated server-side before storing. Validation is configured via a flat `allowed_types: list[str]` (accepting both MIME types like `"image/jpeg"` and extensions like `".pdf"`) plus `max_size: int` (bytes). This simple API avoids separate MIME/extension configuration.

**Spec**: `docs/specs/file-uploads.md`
**Depends on**: #387 (SDD approval)

## Scenarios

**Scenario: file within max_size passes validation**
  Given `max_size=5_000_000` (5MB)
  When  a 2MB file is validated
  Then  validation passes with no errors

**Scenario: file exceeding max_size is rejected**
  Given `max_size=5_000_000` (5MB)
  When  a 10MB file is validated
  Then  a `FileValidationError` is raised with message "File size exceeds 5 MB limit"

**Scenario: file matching allowed MIME type passes**
  Given `allowed_types=["image/jpeg", "image/png"]`
  When  a file with `content_type="image/jpeg"` is validated
  Then  validation passes

**Scenario: file not matching any allowed type is rejected**
  Given `allowed_types=["image/jpeg", "image/png"]`
  When  a file with `content_type="application/pdf"` is validated
  Then  a `FileValidationError` is raised listing allowed types

## Acceptance Criteria

- [ ] `src/hyperadmin/uploads/validation.py` provides `validate_upload(file: UploadFile, *, allowed_types: list[str], max_size: int) -> None`
- [ ] MIME type entries (no dot prefix) matched against `file.content_type`
- [ ] Extension entries (dot prefix like `".pdf"`) matched against `file.filename` suffix
- [ ] `FileValidationError(ValueError)` raised with user-friendly message on failure
- [ ] Sensible defaults if called without explicit params: `max_size=10_000_000` (10MB), `allowed_types=[]` (all types allowed)
- [ ] Unit tests covering all four scenarios + edge cases (empty file, None filename)

## Files Likely Affected

- `src/hyperadmin/uploads/validation.py` (new)
- `src/hyperadmin/uploads/__init__.py` (add export)
- `tests/unit/test_file_validation.py` (new)

## Notes for Implementer

- The `accept` attribute for `<input type="file">` should be derivable from `allowed_types` (pass-through: MIME types and extensions both work in the HTML `accept` attribute directly)
- Keep `validation.py` under 100 lines — single function + one exception class
- No external dependency beyond what's already in the project

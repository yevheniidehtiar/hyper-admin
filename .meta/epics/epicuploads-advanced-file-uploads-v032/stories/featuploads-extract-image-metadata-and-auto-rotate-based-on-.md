---
type: story
id: tvvNBBBLGFl9
title: "feat(uploads): extract image metadata and auto-rotate based on EXIF"
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
  issue_number: 408
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:802a86a99bfc483c71b3c8fbc08bc69c2960197c5012d431be07d88548d73dd3
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:17:30Z
updated_at: 2026-03-31T21:17:30Z
---

## Context

Extracts image metadata (dimensions, format) and auto-rotates images based on EXIF orientation tag using Pillow. Applied at upload time.

**Depends on**: #404

## Scenarios

**Scenario: extract dimensions from uploaded image**
  Given a JPEG image `3000x2000`
  When  `extract_metadata(file)` is called
  Then  the result includes `width=3000`, `height=2000`, `format="JPEG"`

**Scenario: auto-rotate based on EXIF orientation tag**
  Given a JPEG with EXIF orientation tag = 6 (rotated 90° CW by camera)
  When  the image is processed via `auto_rotate(image)`
  Then  the image is rotated to correct orientation before storage

**Scenario: non-image file returns None metadata**
  Given a PDF file
  When  `extract_metadata(file)` is called
  Then  the result is `None` (no exception raised)

## Acceptance Criteria

- [ ] `src/hyperadmin/uploads/metadata.py` with `extract_metadata(file) -> ImageMetadata | None` and `auto_rotate(img) -> Image`
- [ ] `ImageMetadata` dataclass: `width: int`, `height: int`, `format: str`
- [ ] Uses `Image.getexif()` and `ImageOps.exif_transpose()` from Pillow
- [ ] `extract_metadata()` catches all Pillow exceptions, returns `None` for non-images
- [ ] `auto_rotate()` called automatically in the upload processing pipeline (in `_extract_form_data`)
- [ ] Unit tests for all three scenarios

## Files Likely Affected

- `src/hyperadmin/uploads/metadata.py` (new)
- `src/hyperadmin/uploads/__init__.py`
- `src/hyperadmin/views/dynamic.py` (apply auto_rotate in upload pipeline)
- `tests/unit/test_metadata.py` (new)

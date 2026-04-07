---
type: story
id: jYfHoBBIF499
title: "feat(uploads): add thumbnail generation helper using Pillow"
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
  issue_number: 404
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:454720dc972e17e59953953d60f8a6f82afe542ae53d5e5b9e4759f73e7d9900
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:16:35Z
updated_at: 2026-03-31T21:16:35Z
---

## Context

Generates cached thumbnails for image fields. Uses Pillow (already in `pyproject.toml`). Thumbnails are stored in a `.thumbs/` subdirectory alongside the originals and re-used on subsequent requests.

**Depends on**: v0.3.1 complete

## Scenarios

**Scenario: generate thumbnail preserving aspect ratio**
  Given an image `1920x1080`
  When  `generate_thumbnail(storage, filename, max_size=(200, 200))` is called
  Then  the thumbnail is `200x112` (landscape, aspect ratio preserved)

**Scenario: thumbnail is cached on second call**
  Given a thumbnail was already generated for `photo.jpg` at `(200, 200)`
  When  `generate_thumbnail()` is called again with the same params
  Then  the cached thumbnail path is returned without re-processing

**Scenario: corrupt image returns placeholder**
  Given an image file that cannot be opened by Pillow
  When  `generate_thumbnail()` is called
  Then  a placeholder image path is returned and no exception is raised

**Scenario: thumbnail path includes size suffix**
  Given `photo.jpg` in storage
  When  `generate_thumbnail(storage, "photo.jpg", max_size=(100, 100))` is called
  Then  the thumbnail is stored at `.thumbs/photo_100x100.jpg`

## Acceptance Criteria

- [ ] `src/hyperadmin/uploads/thumbnails.py` with `generate_thumbnail(storage, filename, max_size=(200, 200)) -> str`
- [ ] Uses `Image.thumbnail()` from Pillow (ANTIALIAS/LANCZOS resampling)
- [ ] Caches in `.thumbs/{name}_{w}x{h}{ext}` within the storage path
- [ ] Returns cached path if exists (no regeneration)
- [ ] Handles `OSError`, `UnidentifiedImageError` gracefully — returns placeholder path
- [ ] Works with local `FileSystemStorage`; S3 deferred (download-process-upload if needed)
- [ ] Unit tests covering all four scenarios

## Files Likely Affected

- `src/hyperadmin/uploads/thumbnails.py` (new)
- `src/hyperadmin/uploads/__init__.py` (add export)
- `tests/unit/test_thumbnails.py` (new)

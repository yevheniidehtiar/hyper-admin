---
type: epic
id: WxqTdgad9Lx_
title: "epic(uploads): Advanced File Uploads -- v0.3.2"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:uploads
milestone_ref:
  id: VwZbJA2g2bAG
github:
  issue_number: 410
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:63b92429d38400e7981e5dcc69ac89f31bfc3c73b6ebf1b33b601907383fad32
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-03-31T21:17:53Z
updated_at: 2026-03-31T21:17:54Z
---

## Overview

Advanced file upload features: S3-compatible cloud storage, rich ImagePreviewWidget with drag-and-drop, thumbnail generation, EXIF auto-rotation, upload progress bars, and error recovery.

**Prerequisite**: v0.3.1 MVP File Uploads must be complete.

## Tasks

- [ ] #402 feat(uploads): S3-compatible storage backend
- [ ] #403 feat(views): ImagePreviewWidget with drag-and-drop
- [ ] #404 feat(uploads): thumbnail generation (Pillow)
- [ ] #405 feat(ui): enhanced drag-and-drop UX
- [ ] #406 feat(ui): upload progress bar (htmx:xhr:progress)
- [ ] #407 feat(ui): error recovery + retry button
- [ ] #408 feat(uploads): EXIF metadata + auto-rotate
- [ ] #409 feat(views): thumbnails in list/detail views

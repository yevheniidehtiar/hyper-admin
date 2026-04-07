---
type: story
id: 6hHxUgP4koiu
title: "feat(views): display file fields in list and detail views"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - area:templates
  - size:M
estimate: null
epic_ref:
  id: P6jeUKkioZJh
github:
  issue_number: 396
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:086751bdf2b3760604a9e300d7a1dfb3426342086ba561bdb3462318c25538b4
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:13:58Z
updated_at: 2026-04-01T20:57:11Z
---

## Context

File and image fields need special rendering in the read-only list and detail views: filenames become download links, image fields show a preview, and empty fields show an em dash.

**Spec**: `docs/specs/file-uploads.md`
**Depends on**: #389, #391

## Scenarios

**Scenario: file field shows download link in detail view**
  Given a `Product` with `document="report.pdf"`
  When  the detail view is rendered
  Then  `"report.pdf"` is displayed as a clickable `<a>` download link pointing to the file URL

**Scenario: image field shows inline preview in detail view**
  Given a `Product` with `photo="product.jpg"`
  When  the detail view is rendered
  Then  an `<img>` tag with `src` pointing to the storage URL is displayed

**Scenario: file field shows filename in list view**
  Given a `Product` with `document="report.pdf"`
  When  the list view is rendered
  Then  the `document` column shows `"report.pdf"` as text (not the raw storage path)

**Scenario: empty file field shows em dash in list and detail**
  Given a `Product` with `document=None`
  When  the list or detail view is rendered
  Then  the `document` field shows `"—"` (em dash)

## Acceptance Criteria

- [ ] `DynamicModelView` detects file fields in the fetched record data and enriches them with display metadata (URL, filename, type)
- [ ] Detail view renders file fields as `<a href="{url}" download data-testid="file-link-{field_name}">filename</a>`
- [ ] Detail view renders image fields as `<img src="{url}" data-testid="file-preview-{field_name}" alt="{field_label}">`
- [ ] List view renders file field columns as plain filename text (truncated if long)
- [ ] `None` / empty values render as `—` in both views
- [ ] Unit tests covering all four scenarios

## Files Likely Affected

- `src/hyperadmin/views/dynamic.py` (enrich file field values with URLs)
- `src/hyperadmin/templates/detail.html` (conditional file/image rendering)
- `src/hyperadmin/templates/components/table.html` (file column rendering)
- `tests/unit/test_file_display.py` (new)

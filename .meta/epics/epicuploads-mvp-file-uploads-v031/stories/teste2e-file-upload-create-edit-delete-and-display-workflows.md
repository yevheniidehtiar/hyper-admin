---
type: story
id: d-oD0lCA2B96
title: "test(e2e): file upload create, edit, delete, and display workflows"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:L
estimate: null
epic_ref:
  id: P6jeUKkioZJh
github:
  issue_number: 398
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:aa6aadfd2da4405aac40d461802703739026c811fdeedc8340b01d94434fa5b5
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:14:41Z
updated_at: 2026-04-01T20:57:15Z
---

## Context

End-to-end Playwright tests covering the full file upload user journey in the admin UI. Uses accessibility-first locators per CLAUDE.md conventions.

**Depends on**: All v0.3.1 feat issues (#388–#396)

## Scenarios

**Scenario: create record with file upload**
  Given the admin is mounted with a model having a `FileType` column `document`
  When  the user navigates to the create form, attaches `test_report.pdf`, and submits
  Then  the record is created and the list view shows `"test_report.pdf"` in the document column

**Scenario: edit record replaces existing file**
  Given a record with `document="old.pdf"` exists
  When  the user opens the edit form, attaches `new.pdf`, and saves
  Then  the detail view shows a download link for `"new.pdf"`

**Scenario: detail view shows download link for file field**
  Given a record with `document="report.pdf"` exists
  When  the user navigates to the detail view
  Then  a clickable download link with text `"report.pdf"` is visible

**Scenario: delete record cleans up file from storage**
  Given a record with `document="to_delete.pdf"` exists in the temp upload directory
  When  the record is deleted via the admin
  Then  the file `to_delete.pdf` is no longer present in the temp directory

**Scenario: file validation error is shown in form**
  Given a `FileType` field with `max_size=100` bytes
  When  the user attaches a 1KB file and submits
  Then  a validation error message is displayed within the form
  And   the file input is preserved (not reset) for retry

**Scenario: image field shows preview in edit form**
  Given an existing record with `photo="product.jpg"` (an ImageType field)
  When  the user opens the edit form
  Then  the current image filename `"product.jpg"` is displayed near the file input

## Acceptance Criteria

- [ ] `tests/e2e/test_file_upload.py` with one test function per scenario, named after the scenario title
- [ ] Inline `# Given / # When / # Then` comments in every test function
- [ ] Locators use `get_by_role()`, `get_by_label()`, `get_by_test_id()` — NO `.locator('.ha-*')`
- [ ] Fixtures in `tests/e2e/conftest.py` create a SQLModel with `FileType` / `ImageType` columns, backed by `FileSystemStorage` in a `tmp_path` directory
- [ ] Fixtures register the model with the admin and provide a running test server
- [ ] All 6 scenarios pass in CI

## Files Likely Affected

- `tests/e2e/test_file_upload.py` (new)
- `tests/e2e/conftest.py` (new fixtures)

## Notes for Implementer

- `data-testid` to add: `file-input-{field_name}`, `file-link-{field_name}`, `file-preview-{field_name}` (already specified in issues #391 and #396)
- Use `page.set_input_files(locator, file_path)` for Playwright file upload
- Temp upload dir via `tmp_path` pytest fixture — clean up automatically after each test

---
type: story
id: 9MRyFKoOWDFM
title: "feat(ui): add upload error recovery with retry button"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:templates
  - size:M
  - area:frontend
estimate: null
epic_ref:
  id: tIHHxFEv8ZzJ
github:
  issue_number: 407
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a3b1130383004ae71985e275be341656257df40abed83dac4a0109106df59d0f
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:17:15Z
updated_at: 2026-03-31T21:17:16Z
---

## Context

Distinguishes retryable network errors from non-retryable server validation errors. Network errors show a "Retry" button that re-sends the cached file reference.

**Depends on**: #406

## Scenarios

**Scenario: network error shows retry button**
  Given an upload is in progress
  When  the network connection is lost and `htmx:responseError` fires with status 0
  Then  an error message "Upload failed — check your connection" is displayed
  And  a "Retry" button is shown

**Scenario: retry re-sends the same file**
  Given an upload failed with a network error
  When  the user clicks "Retry"
  Then  the same file is re-uploaded from the cached File reference
  And  the progress bar resets to 0

**Scenario: server validation error shown without retry**
  Given the server rejects a file with HTTP 422
  When  the error response is received
  Then  the server's error message is displayed inline
  And  no "Retry" button is shown (user must fix the file)

## Acceptance Criteria

- [ ] `htmx:responseError` listener distinguishes `status == 0` (network) vs `status == 422` (validation)
- [ ] Network error → show "Retry" button + user-friendly message
- [ ] Validation error → show server error message (from JSON response body), no retry
- [ ] "Retry" re-uses the cached `File` object (stored in Alpine.js data)
- [ ] Progress bar resets to 0 on retry

## Files Likely Affected

- `src/hyperadmin/templates/widgets/image_preview_input.html`

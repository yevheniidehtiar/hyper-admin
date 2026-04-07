---
type: story
id: MfkSCZJGaaFR
title: "feat(ui): add upload progress bar using htmx:xhr:progress"
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
  issue_number: 406
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:4f1bcd8047abe54ce0618dbd2dcdc63f31a844c2c645777f2ff320ca0e87e04d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:17:03Z
updated_at: 2026-03-31T21:17:03Z
---

## Context

Shows upload progress using HTMX's native `htmx:xhr:progress` event — no XHR workaround or custom XMLHttpRequest needed.

**HTMX pattern**:
```javascript
htmx.on('#upload-form', 'htmx:xhr:progress', function(evt) {
  htmx.find('#upload-progress').setAttribute(
    'value', evt.detail.loaded / evt.detail.total * 100
  );
});
```

**Depends on**: #403

## Scenarios

**Scenario: progress bar appears during upload**
  Given a file upload is in progress
  When  `htmx:xhr:progress` fires with 50% loaded
  Then  a progress bar shows 50% complete

**Scenario: progress bar shows bytes transferred**
  Given a 5MB file is uploading
  When  2MB has been transferred
  Then  the label shows "2.0 MB / 5.0 MB (40%)"

**Scenario: progress bar transitions to success state**
  Given a file upload reaches 100%
  When  the server response is received
  Then  the progress bar transitions to a success state
  And  the file preview is shown

## Acceptance Criteria

- [ ] `<progress>` element with `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`
- [ ] Alpine.js data drives the `value` attribute
- [ ] `htmx:xhr:progress` listener updates Alpine.js data
- [ ] Bytes label formatted as human-readable (e.g., "2.0 MB / 5.0 MB (40%)")
- [ ] Resets to 0 on new file selection
- [ ] Only visible during active upload (hidden otherwise)

## Files Likely Affected

- `src/hyperadmin/templates/widgets/image_preview_input.html`

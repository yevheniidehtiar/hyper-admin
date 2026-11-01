---
type: story
id: st-rh-00
title: "docs(spec): write and approve the record history SDD"
status: backlog
priority: medium
assignee: null
labels:
  - size:S
  - planned
  - area:docs
  - layer:gate
  - needs-human
estimate: null
epic_ref:
  id: ep-rh-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Record history shows who changed what and when, as a timeline tab on the detail page with field diffs. Write `docs/specs/record-history.md` covering: storage (a `hyperadmin_log_entry` table vs adapter hooks), capture points (create/update/delete, bulk and inline edits), sensitive-field redaction, retention, the detail-panel tab, and alignment with the permissions-matrix audit log (v0.5.7). Then break it into stories.

## Files to Change

- **New:** `docs/specs/record-history.md`

## Acceptance Criteria

- [ ] SDD written from `docs/specs/TEMPLATE.md`
- [ ] Aligned with the audit log in `epic-v057-permissions-matrix` (one log, not two)
- [ ] Owner approves; stories created under this epic

## Blocked by

- none

## Parent

- Epic: `epic-record-history`

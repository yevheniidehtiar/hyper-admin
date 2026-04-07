---
type: story
id: PEAd-3m6oKWX
title: "review(spec): approve SDD for file upload system"
status: done
priority: medium
assignee: null
labels:
  - area:docs
  - size:S
  - approved
  - needs-human
estimate: null
epic_ref:
  id: P6jeUKkioZJh
github:
  issue_number: 387
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e0a233476947352c088cbea84bf5d415ee2362ac6e905c41409e10d80240108d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:11:12Z
updated_at: 2026-04-01T20:56:53Z
---

## Context

The file upload feature introduces a new `uploads/` domain module and touches 3+ top-level modules (`core/`, `views/`, `adapters/`, `uploads/`). Per `sdd-conventions.md`, an SDD is **mandatory** when:
- A feature touches >= 2 top-level modules
- A feature introduces a new domain (new module/package)

This is the **human gate** — implementation sub-tasks (#388–#396) are blocked until this SDD is approved.

**Spec**: `docs/specs/file-uploads.md`

## Scope — What the SDD Must Cover

The SDD must design the complete file upload system:

- **FileField / ImageField** column types for SQLAdmin models
- **Storage backends** — local filesystem + S3-compatible (pluggable via adapter pattern)
- **Upload endpoint** — secure multipart upload handling
- **Image preview widget** — drag-and-drop zone with client-side preview
- **File lifecycle** — upload, replace, delete (cleanup on record deletion)
- **Validation** — file size limits, allowed MIME types, image dimensions

## SDD Review Checklist

The human reviewer verifies the SDD against these criteria (from `sdd-conventions.md`):

- [x] **Problem statement** is clear and scoped
- [x] **Goals** are measurable
- [ ] **Non-goals** prevent over-engineering
- [ ] **BDD scenarios** cover happy path + >= 1 failure path per feature area
- [ ] **Data model changes** are backward compatible (or migration is documented)
- [ ] **API changes** don't break `__init__.py` exports without a semver bump
- [ ] **Edge cases** are enumerated (large files, concurrent uploads, storage failures)
- [ ] **Open questions** are resolved (or explicitly deferred with justification)
- [ ] **Architecture** respects CONSTITUTION.md (no circular imports, dependency direction, no `utils.py`)
- [ ] **Storage adapter** follows the adapter pattern in `adapters/`

## Acceptance Criteria

- [ ] `docs/specs/file-uploads.md` exists with all SDD template sections filled
- [ ] SDD status is `Draft` when first committed
- [ ] Human reviewer approves — status updated to `Approved`
- [ ] All implementation sub-tasks (#388–#396) reference `Spec: docs/specs/file-uploads.md`
- [ ] Implementation sub-tasks are unblocked after approval

## Notes for Reviewer

This is a **human gate** — not an agent implementation task. The planning agent writes the SDD draft; the human reviews against the checklist above and approves or requests changes.

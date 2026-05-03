---
type: story
id: I18nMain_C0PM
title: "chore(pm): create i18n SDD and epic backlog for v0.4.1"
status: in_progress
priority: high
assignee: null
labels:
  - size:S
  - planned
  - i18n
  - cycle:0
estimate: null
epic_ref:
  id: I18nMain_01
github: null
created_at: 2026-05-03T00:00:00Z
updated_at: 2026-05-03T00:00:00Z
---

## Summary

Author the v0.4.1 i18n design document and seed the epic backlog so Cycle 1+ stories
can be dispatched in parallel after human approval.

This is the Cycle 0 / human-gate task per `.claude/rules/sdd-conventions.md`. It does
not modify production code -- only `docs/specs/i18n.md` and `.meta/`.

## Scenarios

**Scenario: SDD draft exists at the canonical path**
  Given the v0.4.1 milestone is `in_progress`
  When  this task completes
  Then  `docs/specs/i18n.md` exists with status **Draft**
  And   the file follows `docs/specs/TEMPLATE.md` section structure

**Scenario: epic file references the SDD**
  Given the i18n epic is created
  When  inspecting `.meta/epics/epic-i18n/epic.md`
  Then  the body contains `**Spec:** docs/specs/i18n.md`
  And   `milestone_ref.id` is `ulcysRt0fus6` (v0.4.1)

**Scenario: human approves the SDD before C1 starts**
  Given the SDD is in **Draft** status
  When  a human reviewer marks it **Approved**
  Then  Cycle 1 stories (C1-A, C1-B) become unblocked
  And   the SDD frontmatter `Status` field is updated

## Tasks

- [x] Create `.meta/epics/epic-i18n/epic.md` linking milestone v0.4.1
- [x] Create `.meta/epics/epic-i18n/stories/chorepm-create-i18n-sdd.md` (this file)
- [x] Write `docs/specs/i18n.md` from `docs/specs/TEMPLATE.md` (status: Draft)
- [ ] Open PR and request human review of the SDD
- [ ] On approval, flip SDD `Status` -> `Approved` and dispatch C1-A + C1-B

## Acceptance criteria

- [ ] `docs/specs/i18n.md` exists, status: Draft
- [ ] Epic at `.meta/epics/epic-i18n/epic.md` exists and links the SDD
- [ ] `./scripts/gitpm.sh validate` exits 0
- [ ] PR opened with the SDD + epic + this story
- [ ] Human-approval comment on the PR flips SDD status to Approved before C1 dispatch

## Files to modify

- `docs/specs/i18n.md` (new) -- SDD draft
- `.meta/epics/epic-i18n/epic.md` (new) -- epic descriptor
- `.meta/epics/epic-i18n/stories/chorepm-create-i18n-sdd.md` (new) -- this story

## Demo checkpoint

`./scripts/gitpm.sh validate` exits 0 and `docs/specs/i18n.md` renders cleanly in
a markdown preview. Human review on the PR is the gate.

## Agent

- **Size:** S
- **Tier:** Sonnet (planning)
- **blocked_by:** none (this is the Cycle 0 gate)

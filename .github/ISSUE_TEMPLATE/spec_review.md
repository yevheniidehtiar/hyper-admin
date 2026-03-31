---
name: Spec Review (SDD Human Gate)
about: Review and approve a Software Design Document before implementation begins
title: "review(spec): approve SDD for "
labels: ["needs-human"]
---

## Context

<!-- Explain why an SDD is required for this feature. Which top-level modules are affected?
     Link to the spec file: docs/specs/{slug}.md -->

This feature touches <!-- list modules, e.g. `core/`, `views/`, `adapters/`, `uploads/` --> and
introduces <!-- new domain / changes public API / is size:L -->. Per `sdd-conventions.md`, an SDD is **mandatory**.

This is the **human gate** — all implementation sub-tasks are blocked until this SDD is approved.

**Spec**: `docs/specs/{slug}.md`

## Scope — What the SDD Must Cover

<!-- List the key design areas the SDD must address. Example: -->

- <!-- Core data model / field types -->
- <!-- Backend logic / services -->
- <!-- API / endpoint changes -->
- <!-- Configuration changes (`Admin()`, `AdminOptions`, env vars) -->
- <!-- Integration with existing modules -->
- <!-- File lifecycle / cleanup / validation -->

## SDD Review Checklist

The human reviewer verifies the SDD against these criteria (from `sdd-conventions.md`):

- [ ] **Problem statement** is clear and scoped
- [ ] **Goals** are measurable
- [ ] **Non-goals** prevent over-engineering
- [ ] **BDD scenarios** cover happy path + >= 1 failure path per feature area
- [ ] **Data model changes** are backward compatible (or migration is documented)
- [ ] **API changes** don't break `__init__.py` exports without a semver bump
- [ ] **Edge cases** are enumerated
- [ ] **Open questions** are resolved (or explicitly deferred with justification)
- [ ] **Architecture** respects CONSTITUTION.md (no circular imports, dependency direction, no `utils.py`)

## Acceptance Criteria

- [ ] `docs/specs/{slug}.md` exists with all SDD template sections filled
- [ ] SDD status is `Draft` when first committed
- [ ] Human reviewer approves — status updated to `Approved`
- [ ] All implementation sub-tasks reference `Spec: docs/specs/{slug}.md`
- [ ] Implementation sub-tasks are unblocked after approval

## Notes for Reviewer

This is a **human gate** — not an agent implementation task. The agent writes the SDD draft; the human reviews against the checklist above and approves or requests changes.

Per `sdd-conventions.md`: an SDD in `Draft` or `In Review` status **blocks all implementation sub-tasks**.

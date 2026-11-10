---
type: story
id: st-autopilot-04
title: "docs(agentic-workflow): autopilot"
status: done
priority: medium
assignee: null
labels:
  - size:M
  - planned
  - documentation
estimate: null
epic_ref:
  id: ep-autopilot-01
created_at: 2026-11-10T00:00:00Z
updated_at: 2026-11-10T00:00:00Z
---

## Summary

The agentic-workflow docs describe the conductor pipeline, a `main` branch and `just` commands. Rewrite them for the
autopilot: the epic-branch model, the tick and its jobs, the label machine, what the owner still does (one approval
per epic, hotfix and Dependabot PRs to `develop`, hard-stop questions in the daily digest), and how to install, dry-run
and stop the launchd agent.

Contributor docs get the same sweep: `main` to `develop`, `just` to `poe`, epic branches, and a merge-hygiene section.
In `docs/contributing.md` this story owns the `## Merge hygiene` heading and writes two subsections under it,
`### Story status` (open-epic and close-epic commits, `ap:*` labels) and `### Conflicting PRs` (the autopilot rebases
them). Those were planned as stubs for st-conflict-03/04, which are now cancelled. st-conflict-01 and st-conflict-02
afterwards add only `### Dependencies` and `### Releases` under the existing heading.
`justfile release` points at `master`. `scripts/setup-github.sh` creates the new labels (`ai-approved`,
`ai-changes-requested`, `ap:in-progress`, `ap:in-review`, `ap:done`, `superseded`) and drops the merge-queue labels.

## Files to Change

- `docs/agentic-workflow/index.md`, `orchestration.md`, `dev-agents.md`, `onboarding-agents.md`,
  `onboarding-humans.md`, `roadmap-planning-agent.md`
- `docs/agentic-workflow/system-diagram.svg`
- `CONTRIBUTING.md` — `main` to `develop`, `just` to `poe`, epic branches
- `docs/contributing.md` — the same sweep, plus `## Merge hygiene` with `### Story status` and
  `### Conflicting PRs` (no `### Dependencies` or `### Releases`; those belong to st-conflict-01/02)
- `justfile` — `release` recipe only: `main` to `master` (own hunk; st-autopilot-02 appends aliases elsewhere)
- `scripts/setup-github.sh` — new labels, merge-queue labels removed

## Scenarios

```
Scenario: A new contributor finds the right base branch
  Given a reader of CONTRIBUTING.md
  When  they look for the branch to target
  Then  the page names develop for standalone PRs and epic/<slug> for story PRs
  And   no page mentions a main branch

Scenario: The owner can operate the autopilot from the docs
  Given the orchestration page
  When  the owner wants to install, dry-run, inspect or stop the autopilot
  Then  each of those has a documented poe command

Scenario: Label setup matches the label machine
  Given a fresh repository
  When  scripts/setup-github.sh runs
  Then  the labels ai-approved, ai-changes-requested, needs-human, ap:in-progress, ap:in-review, ap:done and superseded exist
  And   no merge-queue label is created
```

## Acceptance Criteria

- [ ] A new contributor finds the right base branch
- [ ] The owner can operate the autopilot from the docs
- [ ] Label setup matches the label machine
- [ ] The docs no longer describe the conductor, the delivery manager or the `.meta` lock PR
- [ ] `docs/contributing.md` has one `## Merge hygiene` heading with `### Story status` and `### Conflicting PRs`
- [ ] `poe docs:build` passes

## Blocked by

- `ciautopilot-epic-branch-lane` (st-autopilot-01) — merges first
- `featautopilot-local-supervisor` (st-autopilot-02) — shares `justfile`; also the commands and paths the docs describe

## Parent

- Epic: `epic-autopilot`

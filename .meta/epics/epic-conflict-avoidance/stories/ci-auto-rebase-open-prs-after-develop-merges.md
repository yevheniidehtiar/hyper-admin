---
type: story
id: st-conflict-04
title: "ci: auto-rebase open PRs after develop merges"
status: todo
priority: medium
assignee: null
labels:
  - size:S
  - planned
  - area:ci
estimate: null
epic_ref:
  id: ep-conflict-avoidance-01
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

Under rebase-only merges, open PRs fall behind `develop` after every merge, and conflicts surface late. The head
session currently loops `gh pr update-branch --rebase` by hand. Replace it with a workflow on `push` to `develop` that
rebases every open, non-draft PR targeting `develop` via `gh pr update-branch --rebase`, using the bot token so the
rewritten commits stay bot-committed. PRs that cannot be rebased cleanly get a `needs-rebase` label and a comment
instead of failing the job; the label is removed on the next clean rebase.

## Files to Change

- `.github/workflows/auto-rebase.yml` (new) — trigger on `push: develop`, concurrency group, bot token
- `docs/contributing.md` — fill the `### Auto-rebase` stub only

## Scenarios

```
Scenario: Open PRs are rebased after a merge
  Given two open PRs targeting develop that are behind
  When  a PR is merged into develop
  Then  both PRs are rebased onto the new develop by the bot account

Scenario: Conflicting PR is labelled, not failed
  Given an open PR that conflicts with the new develop
  When  the workflow runs
  Then  the PR gets the needs-rebase label and a comment, and the job succeeds

Scenario: Drafts are skipped
  Given an open draft PR targeting develop
  When  the workflow runs
  Then  the draft is not rebased
```

## Acceptance Criteria

- [ ] Open PRs are rebased after a merge
- [ ] Conflicting PR is labelled, not failed
- [ ] Drafts are skipped
- [ ] Commits are attributed to the bot account, not a maintainer
- [ ] `poe lint` passes

## Blocked by

- `builddeps-one-lane-dependency-policy-uv-lock-regeneration-c` (st-conflict-01) — creates the `docs/contributing.md` stub

## Parent

- Epic: `epic-conflict-avoidance`

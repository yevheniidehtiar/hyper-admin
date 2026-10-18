---
type: story
id: st-conflict-04
title: "ci: detect and label conflicting PRs after develop merges"
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

A merge into `develop` can leave other open PRs `CONFLICTING`, and today nobody notices until merge time. Pre-emptive
rebases are not the fix: the `develop` ruleset does not require up-to-date branches
(`strict_required_status_checks_policy: false`), the rebase merge rebases at merge time anyway, and every push
restarts CI and dismisses approvals (`dismiss_stale_reviews_on_push: true`).

Add a workflow on `push` to `develop` that lists the open PRs targeting `develop`, waits for GitHub to compute
`mergeable`, and for each `CONFLICTING` PR adds a `needs-rebase` label and one comment that tags the author with the
rebase recipe (`git pull --rebase origin develop`, resolve, `git push --force-with-lease`). PRs that are no longer
conflicting lose the label. The workflow never pushes to PR branches.

## Files to Change

- `.github/workflows/conflict-check.yml` (new) — trigger on `push: develop`, concurrency group, `pull-requests: write`
- `docs/contributing.md` — fill the `### Conflicting PRs` stub only

## Scenarios

```
Scenario: Conflicting PR is labelled and its author pinged
  Given an open PR that conflicts with develop after a merge
  When  the workflow runs
  Then  the PR gets the needs-rebase label and one comment tagging its author

Scenario: Clean PRs are left alone
  Given an open PR that is behind develop but merges cleanly
  When  the workflow runs
  Then  it is not labelled, commented on or pushed to

Scenario: Label is removed once resolved
  Given a PR labelled needs-rebase that is no longer conflicting
  When  the workflow runs
  Then  the needs-rebase label is removed

Scenario: No duplicate comments
  Given a PR already labelled needs-rebase that still conflicts
  When  the workflow runs again
  Then  no second comment is posted
```

## Acceptance Criteria

- [ ] Conflicting PR is labelled and its author pinged
- [ ] Clean PRs are left alone
- [ ] Label is removed once resolved
- [ ] No duplicate comments
- [ ] `UNKNOWN` mergeable state is retried briefly, then skipped without failing the job
- [ ] `poe lint` passes

## Blocked by

- `builddeps-one-lane-dependency-policy-uv-lock-regeneration-c` (st-conflict-01) — creates the `docs/contributing.md` stub

## Parent

- Epic: `epic-conflict-avoidance`

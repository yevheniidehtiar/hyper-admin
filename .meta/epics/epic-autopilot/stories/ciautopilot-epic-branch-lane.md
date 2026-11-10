---
type: story
id: st-autopilot-01
title: "ci(autopilot): epic branch lane"
status: done
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:ci
estimate: null
epic_ref:
  id: ep-autopilot-01
created_at: 2026-11-10T00:00:00Z
updated_at: 2026-11-10T00:00:00Z
---

## Summary

Story PRs will target `epic/<slug>` instead of `develop`. `pull_request.branches` filters on the base branch, so today
such a PR gets no CI at all. Add `epic/**` to the PR triggers of the CI, Test and GitPM Sync workflows. In `test.yml`
also add `epic/**` to `push.branches` and skip the matrix job on epic-branch pushes
(`!startsWith(github.ref, 'refs/heads/epic/')`), so a story merge runs Lint and the three E2E shards on the
integrated state but not the 8-row matrix. `ci.yml` push stays `develop`/`master` only.

Housekeeping in the same hotspot: `loadtest.yml` references a `main` branch that does not exist, `code-review.yml` is
dead (`if: false`, API-key based), there is no `CODEOWNERS` although the `develop` ruleset requires code-owner review,
and the PR template lacks the `Story: <story-id>` line the autopilot maps PRs with.

`scripts/secure-repo.sh` stores the payload of a new ruleset `epic-branches` on `refs/heads/epic/**` with exactly one
rule, `required_linear_history`. No `required_status_checks` (it would reject the bot's rebase force-push), no
`pull_request` rule, no `non_fast_forward`, no `deletion`. The script change only stores the payload; the owner
applies it.

This is the only story that touches `.github/**`. It is pushed under the owner's git credential, because the bot
token lacks the `workflow` scope, and it merges before the other stories.

## Files to Change

- `.github/workflows/ci.yml` — `epic/**` in `pull_request.branches`
- `.github/workflows/test.yml` — `epic/**` in `pull_request.branches` and `push.branches`; matrix job skipped on
  `refs/heads/epic/` pushes
- `.github/workflows/gitpm-sync.yml` — `epic/**` in `pull_request.branches`
- `.github/workflows/loadtest.yml` — `main` to `develop`
- `.github/workflows/code-review.yml` — delete
- `.github/CODEOWNERS` (new) — `* @yevheniidehtiar`
- `.github/PULL_REQUEST_TEMPLATE.md` — `Story:` line, `just` to `poe`
- `scripts/secure-repo.sh` — fix `main`, add the `epic-branches` ruleset payload

## Scenarios

```
Scenario: Story PR against an epic branch gets CI
  Given a PR whose base is epic/some-epic
  When  the PR is opened or updated
  Then  the CI and Test workflows run on it

Scenario: Epic branch push skips the matrix
  Given a story PR was rebase-merged into epic/some-epic
  When  the push run of the Test workflow starts
  Then  Lint and the three E2E shards run
  And   the Python/dependency matrix job is skipped

Scenario: develop keeps its full checks
  Given a push to develop
  When  the Test workflow runs
  Then  the matrix job runs as before
```

## Acceptance Criteria

- [ ] Story PR against an epic branch gets CI
- [ ] Epic branch push skips the matrix
- [ ] develop keeps its full checks
- [ ] No workflow or script references a `main` branch
- [ ] `scripts/secure-repo.sh` contains the `epic-branches` payload with `required_linear_history` as its only rule
- [ ] `poe lint` passes

## Parent

- Epic: `epic-autopilot`

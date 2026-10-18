---
type: story
id: st-conflict-03
title: "ci(meta): set .meta story status from PR merge events"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:ci
  - gitpm
estimate: null
epic_ref:
  id: ep-conflict-avoidance-01
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

Feature PRs and merge-sync PRs both edit a story's `status:` line, so they conflict (#605, #621). Move status changes
out of PRs: a GitHub Action on `pull_request: closed` with `merged == true` finds the story the PR delivered and sets
`status: done` (and `updated_at`) in one bot commit to `develop`. Mapping, in order: a `Story: <story-id>` line in the
PR body or a commit footer, then the branch name containing the story id. A PR that maps to no story does nothing.
Once this lands, the rule in `.claude/rules/conflict-avoidance.md` becomes "nobody edits `status:` by hand".

## Files to Change

- `.github/workflows/meta-status.yml` (new) — trigger, bot token, single commit
- `scripts/meta_status.py` (new) — PR → story id resolution and the front-matter edit
- `tests/unit/test_meta_status.py` (new) — mapping and edit unit tests
- `.github/PULL_REQUEST_TEMPLATE.md` — `Story:` line
- `docs/contributing.md` — fill the `### Story status` stub only

## Scenarios

```
Scenario: Merged PR marks its story done
  Given a PR whose body contains "Story: st-conflict-03"
  When  the PR is merged
  Then  the story file has status done and a fresh updated_at, committed by the bot

Scenario: Branch name is the fallback mapping
  Given a merged PR with no Story line and branch "ci/st-conflict-03-meta-status"
  When  the workflow runs
  Then  st-conflict-03 is marked done

Scenario: Closed without merge changes nothing
  Given a PR closed without merging
  When  the workflow runs
  Then  no commit is made

Scenario: Unmapped PR changes nothing
  Given a merged PR with no story reference
  When  the workflow runs
  Then  no commit is made and the job succeeds
```

## Acceptance Criteria

- [ ] Merged PR marks its story done
- [ ] Branch name is the fallback mapping
- [ ] Closed without merge changes nothing
- [ ] Unmapped PR changes nothing
- [ ] 100 % coverage of `scripts/meta_status.py` changed lines; `poe lint` passes

## Blocked by

- `builddeps-one-lane-dependency-policy-uv-lock-regeneration-c` (st-conflict-01) — creates the `docs/contributing.md` stub

## Parent

- Epic: `epic-conflict-avoidance`

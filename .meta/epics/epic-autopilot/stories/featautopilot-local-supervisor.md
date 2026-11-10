---
type: story
id: st-autopilot-02
title: "feat(autopilot): local supervisor"
status: todo
priority: high
assignee: null
labels:
  - size:L
  - planned
  - area:ci
  - dx
estimate: null
epic_ref:
  id: ep-autopilot-01
created_at: 2026-11-10T00:00:00Z
updated_at: 2026-11-10T00:00:00Z
---

## Summary

`ops/conductor/supervisor.sh` cannot do the job: it runs in plan mode (no edits), needs an API key and has a
list-price budget cap that kills long runs. Replace it with `ops/autopilot/`, driven by a launchd agent
`com.hyperadmin.autopilot` that runs `ops/autopilot/autopilot.sh tick` every 15 minutes.

A tick:

1. Takes a single-instance lock with `mkdir` (macOS has no `flock`) and loads `~/.hyperadmin-autopilot/state.json`
   (cooldown, running jobs, per-PR retry counters, janitor approval).
2. Runs deterministic checks with `gh` and `git` only: red `develop` or nightly runs; open bot PRs that are failing,
   cancelled, `CONFLICTING`, `ai-changes-requested`, or green and `ai-approved`; epics on `epic/**` that need a draft
   PR, an SDD approval or integration; free worker slots (`DEV_AGENT_LIMIT`, default 3, 1 when free memory is under
   4 GB); ready stories (`todo`, not `deferred`, dependencies `done`, no `## Files to Change` overlap with a running
   story and no hotspot owned by one); green Dependabot PRs; janitor candidates.
3. Spawns one headless job per action in the pool worktrees `.claude/worktrees/ap-1..3`, with `AUTOPILOT=1`, a tool
   allowlist instead of skipped permissions, and a wall-clock kill (macOS has no `timeout`). Prompts are read from
   `ops/autopilot/prompts/` in the main checkout: `implement`, `review`, `fix-pr`, `fix-develop`, `approve-sdd`,
   `integrate-epic`, `digest`.
4. Detects a usage limit in a job result and sets `cooldown_until`; deterministic checks keep running during cooldown.
5. Enforces retry budgets: one rerun for a cancelled or timed-out check, 3 fix rounds and 2 review rounds per PR, then
   `needs-human`.

`AUTOPILOT_DRY_RUN=1` prints the planned actions and takes none. The janitor (merged worktrees and branches, job files
older than 7 days) runs as a dry run until the owner approves the first list once.

The `## Files to Change` parser is ported into `ops/autopilot/lib/overlap.py`, so the repo does not depend on a
user-level skill. The `TaskUpdate` hook in `.claude/settings.json` becomes a no-op when `AUTOPILOT=1`.

## Files to Change

- `ops/autopilot/autopilot.sh` (new) — `tick`, install/uninstall/status/logs entry points
- `ops/autopilot/lib/gh.sh`, `ops/autopilot/lib/state.sh` (new) — `gh` queries, lock and state helpers
- `ops/autopilot/lib/ready.py`, `ops/autopilot/lib/overlap.py` (new) — story readiness and touched-files overlap
- `ops/autopilot/prompts/{implement,review,fix-pr,fix-develop,approve-sdd,integrate-epic,digest}.md` (new)
- `ops/autopilot/com.hyperadmin.autopilot.plist.tmpl` (new) — `StartInterval 900`
- `ops/autopilot/README.md` (new)
- `ops/conductor/` — delete
- `pyproject.toml` — poe tasks `autopilot:install|uninstall|status|logs|tick` (own hunk, no dependency change)
- `justfile` — `autopilot` aliases (own hunk, appended)
- `.claude/settings.json` — `TaskUpdate` hook skips when `AUTOPILOT=1`
- `tests/unit/test_autopilot_ready.py`, `tests/unit/test_autopilot_overlap.py`,
  `tests/unit/test_autopilot_state.py` (new) — pure Python, no `gh`

## Scenarios

```
Scenario: Dry run takes no action
  Given AUTOPILOT_DRY_RUN=1
  When  the tick runs
  Then  it prints the planned actions
  And   no job is spawned and nothing is pushed, merged or labelled

Scenario: Only one tick runs at a time
  Given a tick that holds the lock
  When  a second tick starts
  Then  the second tick exits without doing anything

Scenario: A story with unfinished dependencies is not ready
  Given a todo story whose Blocked-by story is not done
  When  readiness is computed
  Then  the story is not dispatched

Scenario: A deferred story is skipped
  Given a todo story labelled deferred
  When  readiness is computed
  Then  the story is not dispatched

Scenario: Overlapping stories do not run together
  Given a running story that lists a file under "## Files to Change"
  And   a ready story that lists the same file
  When  the tick fills free slots
  Then  the second story waits

Scenario: Usage limit starts a cooldown
  Given a job result that reports a usage limit with a reset epoch
  When  the tick reads the result
  Then  cooldown_until is set to that epoch
  And   later ticks spawn no jobs until it passes

Scenario: Retry budget ends in needs-human
  Given a PR that has used its 3 fix rounds
  When  its checks fail again
  Then  the PR gets the needs-human label and no further fix job

Scenario: Green and approved story PR is merged
  Given a story PR with all checks green, the ai-approved label and no needs-human label
  And   the PR is rebased on the epic branch tip
  When  the tick runs
  Then  the PR is rebase-merged into the epic branch and its branch deleted
```

## Acceptance Criteria

- [ ] Dry run takes no action
- [ ] Only one tick runs at a time
- [ ] A story with unfinished dependencies is not ready
- [ ] A deferred story is skipped
- [ ] Overlapping stories do not run together
- [ ] Usage limit starts a cooldown
- [ ] Retry budget ends in needs-human
- [ ] Green and approved story PR is merged
- [ ] `ops/conductor/` is gone and nothing references it
- [ ] `poe test:unit` passes; 100 % coverage of changed Python lines (`poe test:cov-diff`)
- [ ] `uv run ruff check . && uv run ruff format --check .` passes

## Blocked by

- `ciautopilot-epic-branch-lane` (st-autopilot-01) — story PRs against `epic/**` get no CI until it merges

## Parent

- Epic: `epic-autopilot`

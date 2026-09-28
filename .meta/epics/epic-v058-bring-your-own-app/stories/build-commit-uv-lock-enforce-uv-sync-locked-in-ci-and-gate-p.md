---
type: story
id: st-v058-byoa-12
title: "build: commit uv.lock, enforce uv sync --locked in CI and gate PRs to master/develop"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:packaging
  - layer:packaging
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Stop ignoring `uv.lock` (remove `.gitignore:69` and add `!uv.lock` after `.gitignore:104`), commit the lock file, switch CI to `uv sync --locked --all-extras`, and add `pull_request: [master, develop]` triggers.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: E

## Files to Change

- `.gitignore`
- `uv.lock`
- `.github/workflows/ci.yml`
- `.github/workflows/test.yml`

## Scenarios

```
Scenario: CI fails on a stale lock
  Given pyproject changes without a lock update
  When  CI runs uv sync --locked
  Then  the job fails

Scenario: PRs to develop are gated
  Given a pull request targeting develop
  When  it is opened
  Then  the CI workflow runs
```

## Acceptance Criteria

- [ ] CI fails on a stale lock
- [ ] PRs to develop are gated
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `choredeps-audit-runtime-dependencies` (st-v058-byoa-11)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)

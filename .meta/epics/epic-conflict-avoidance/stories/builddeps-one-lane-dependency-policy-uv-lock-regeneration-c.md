---
type: story
id: st-conflict-01
title: "build(deps): one-lane dependency policy + uv.lock regeneration check in CI"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:ci
  - layer:packaging
estimate: null
epic_ref:
  id: ep-conflict-avoidance-01
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

`uv.lock` conflicts are resolved by hand today, and a hand-merged lock can silently drift from `pyproject.toml`
(`uv sync --locked` only catches some of it). Add a dedicated CI step `uv lock --check` that fails when the committed
lock is not what `uv lock` would produce, and document the one-lane policy: dependency, extra and version changes ship
in their own small PR; on a lock conflict, take `origin/develop`'s `uv.lock`, rebase, run `uv lock`, commit.

## Files to Change

- `.github/workflows/ci.yml` — new `lock` job (single Python, no matrix) running `uv lock --check`
- `docs/contributing.md` — new `## Merge hygiene` heading with a full `### Dependencies` subsection (relock recipe)
  and one-line stubs for `### Releases`, `### Story status`, `### Auto-rebase` (seam for st-conflict-02/03/04)

## Scenarios

```
Scenario: CI fails on a hand-merged lock
  Given a PR whose uv.lock differs from what `uv lock` produces
  When  CI runs
  Then  the lock job fails with a message pointing to the relock recipe

Scenario: CI passes on a regenerated lock
  Given a PR that rebased on develop and ran `uv lock`
  When  CI runs
  Then  the lock job passes
```

## Acceptance Criteria

- [ ] CI fails on a hand-merged lock
- [ ] CI passes on a regenerated lock
- [ ] `docs/contributing.md` documents the one-lane policy and the relock recipe
- [ ] `poe lint` passes

## Parent

- Epic: `epic-conflict-avoidance`

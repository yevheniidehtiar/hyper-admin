---
type: epic
id: ep-conflict-avoidance-01
title: "epic(ci): conflict avoidance — automate the hotspots parallel PRs keep colliding on"
status: todo
priority: high
owner: null
labels:
  - planned
  - area:ci
  - dx
  - size:M
milestone_ref:
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Overview

Parallel PRs keep conflicting after merge. Observed in the week of 2026-10-12: `pyproject.toml` / `uv.lock`
(#626, #639, #640, #643), a manual version bump in `pyproject.toml` (#643), `.meta` status edits in both feature and
sync PRs (#605, #621), shared registration files (`core/app.py`, `__init__` re-exports, `hyperadmin.css` `@import`s,
the sidebar), a long-lived branch 34 commits behind (#624), PRs stacked under rebase-only merges (#641/#643 on #640),
and a `.gitignore` side effect (#639).

The process half is documented in [`.claude/rules/conflict-avoidance.md`](../../../.claude/rules/conflict-avoidance.md).
This epic removes the hotspots that a rule alone cannot: CI and release automation, merge-event status sync, and
discovery seams instead of hand-maintained lists.

## Stories

| ID | Story | Size | Blocked by |
|---|---|---|---|
| st-conflict-01 | [build(deps): one-lane dependency policy + uv.lock regeneration check in CI](stories/builddeps-one-lane-dependency-policy-uv-lock-regeneration-c.md) | S | — |
| st-conflict-02 | [build(release): derive version from git tags](stories/buildrelease-derive-version-from-git-tags.md) | S | st-v058-byoa-50, st-conflict-01 |
| st-conflict-03 | [ci(meta): set .meta story status from PR merge events](stories/cimeta-set-meta-story-status-from-pr-merge-events.md) | M | st-conflict-01 |
| st-conflict-04 | [ci: detect and label conflicting PRs after develop merges](stories/ci-detect-and-label-conflicting-prs-after-develop-merges.md) | S | st-conflict-01 |
| st-conflict-05 | [refactor(core): discover component stylesheets instead of a hand-maintained @import list](stories/refactorcore-discover-component-stylesheets-instead-of-hand.md) | M | v0.5.8 wave (owns `views/**`) |
| st-conflict-06 | [refactor(core): lazy one-line-per-symbol package exports with a drift guard](stories/refactorcore-lazy-one-line-per-symbol-package-exports-with-a.md) | S | st-v058-byoa-50 |
| st-conflict-07 | [refactor(core): route providers instead of hand-wired routes in core/app.py](stories/refactorcore-route-providers-instead-of-hand-wired-routes-in.md) | M | st-v058-byoa-50 |

### Touched-files matrix

| File | 01 | 02 | 03 | 04 | 05 | 06 | 07 |
|---|---|---|---|---|---|---|---|
| `.github/workflows/ci.yml` | x | | | | | | |
| `.github/workflows/release.yml` | | x | | | | | |
| `.github/workflows/meta-status.yml` (new) | | | x | | | | |
| `.github/workflows/conflict-check.yml` (new) | | | | x | | | |
| `pyproject.toml`, `uv.lock` | | x | | | | | |
| `docs/contributing.md` | x | x | x | x | | | |
| `src/hyperadmin/static/css/**`, `views/stylesheets.py` (new) | | | | | x | | |
| `src/hyperadmin/templates/_base.html` | | | | | x | | |
| `src/hyperadmin/__init__.py` | | | | | | x | |
| `src/hyperadmin/core/app.py`, `routing.py` | | | | | | | x |

`docs/contributing.md` is shared by 01–04, so 01 doubles as the seam: it creates `## Merge hygiene` with all four
`###` subsections (Dependencies, Releases, Story status, Conflicting PRs; the last three as one-line stubs). 02–04 then
each fill only their own subsection, in separate hunks. Stories 02, 05, 06 and 07 touch files the v0.5.8 wave owns and
wait for its release story (st-v058-byoa-50).

## Out of scope

- Merge queues or changing the rebase-only merge method.
- Rewriting history of already-merged PRs.

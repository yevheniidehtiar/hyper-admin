---
type: story
id: st-v100-freeze-01
title: "docs: versioning and deprecation policy"
status: done
priority: high
assignee: null
labels:
  - documentation
  - size:S
  - planned
  - area:docs
estimate: null
epic_ref:
  id: ep-v100-freeze-01
created_at: 2026-11-20T00:00:00Z
updated_at: 2026-11-20T00:00:00Z
---

## Summary

Publish the semver and deprecation policy that v1.0 commits to: what the public API is, what may change in a
minor or patch release, how a deprecation is announced and how long it lives, and which Python and dependency
versions are supported.

## Files to Change

- **New:** a policy page under `docs/`
- **Modified:** `zensical.toml` (nav entry)

## Acceptance Criteria

- [ ] The page defines the public API surface and what is explicitly not public
- [ ] Semver rules before and after 1.0 are stated
- [ ] The deprecation process names the warning class, the minimum lifetime and the changelog entry
- [ ] Supported Python and dependency versions match `pyproject.toml` and the CI matrix
- [ ] The owner has reviewed every promise that is not yet practice
- [ ] `poe docs:build` passes

## Parent

- Epic: `epic-v100-api-freeze` (v1.0 — Stable Release)

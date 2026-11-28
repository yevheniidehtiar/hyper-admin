---
type: story
id: st-v100-freeze-02
title: "docs: migration guides from Django admin, SQLAdmin and Flask-Admin"
status: done
priority: medium
assignee: null
labels:
  - documentation
  - size:M
  - planned
  - area:docs
estimate: null
epic_ref:
  id: ep-v100-freeze-01
created_at: 2026-11-20T00:00:00Z
updated_at: 2026-11-20T00:00:00Z
---

## Summary

One guide per framework (RFC #274): a concept mapping table, a step-by-step port of a small admin with
before and after code, auth and permissions mapping, and what has no equivalent yet.

## Files to Change

- **New:** three guide pages under `docs/`
- **Modified:** `zensical.toml` (nav entries)

## Acceptance Criteria

- [ ] Three guides are published and linked from the docs navigation
- [ ] Every HyperAdmin option and API named in a guide exists on `develop`
- [ ] Every HyperAdmin code sample was run
- [ ] Each guide lists what has no equivalent yet
- [ ] `poe docs:build` passes

## Parent

- Epic: `epic-v100-api-freeze` (v1.0 — Stable Release)

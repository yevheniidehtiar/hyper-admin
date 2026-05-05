---
type: story
id: LrSvJLyCHmOl
title: "chore: scaffold plugins/hyperadmin-logfire package"
status: todo
priority: high
assignee: null
labels:
  - chore
  - size:S
  - planned
  - plugins
  - observability
estimate: null
epic_ref:
  id: Plo-enMpTWhB
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Create the empty package skeleton for `hyperadmin-logfire` under
`plugins/hyperadmin-logfire/`. Wire it into the uv workspace so it installs
locally during development.

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **New:** `plugins/hyperadmin-logfire/pyproject.toml`
  - `name = "hyperadmin-logfire"`, `version = "0.1.0"`
  - `dependencies = ["hyper-admin>=0.8.0", "logfire>=4.0"]`
  - `[project.entry-points."hyperadmin.plugins"] logfire = "hyperadmin_logfire:LogfirePlugin"`
- **New:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/__init__.py` —
  re-export `LogfirePlugin`, `instrument_admin`
- **New:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/plugin.py` — empty
  `LogfirePlugin` class with `name = "logfire"` and a no-op `on_register`
- **New:** `plugins/hyperadmin-logfire/README.md`
- **Modified:** root `pyproject.toml` — add `plugins/hyperadmin-logfire` to
  `[tool.uv.workspace.members]` (or equivalent for whatever workspace tooling is in use)
- **Modified:** root `pyproject.toml` — add optional extra
  `[project.optional-dependencies].logfire = ["hyperadmin-logfire>=0.1"]` (pending
  SDD review confirmation)

## Acceptance Criteria

- [ ] `uv sync --all-extras` from repo root installs the new package in editable mode
- [ ] `python -c "import hyperadmin_logfire; print(hyperadmin_logfire.LogfirePlugin)"` succeeds
- [ ] `hyperadmin plugins list` (after Epic 1 stories are merged) shows `logfire` as discovered
- [ ] `poe lint` passes against the new package source
- [ ] `git ls-files plugins/hyperadmin-logfire/` lists exactly the files above

## Blocked by

- `reviewspec-approve-sdd-for-plugin-logfire`

## Parent

- Epic: `epic-plugin-logfire-first-plugin`

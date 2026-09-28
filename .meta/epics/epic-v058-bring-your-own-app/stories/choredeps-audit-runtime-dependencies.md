---
type: story
id: st-v058-byoa-11
title: "chore(deps): audit runtime dependencies"
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

Make the runtime dependency set correct for a PyPI install:
- add `pydantic-settings` (it is imported by `core/settings.py` but not declared);
- add `tzdata; sys_platform == 'win32'`;
- drop `appnope`, `uvicorn` and `httpx`, moving `uvicorn` and `httpx` to dev dependencies;
- change `fastapi[standard]` to `fastapi`;
- remove the duplicate `python-multipart` entry;
- add a one-line justification comment for each dependency that is not obvious (CONSTITUTION §6);
- fix the incorrect GHSA-4xgf-cpjx-pc3j ignore comment.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: E

## Files to Change

- `pyproject.toml`

## Scenarios

```
Scenario: built wheel imports cleanly
  Given the wheel produced by uv build installed in a fresh venv
  When  python -c "from hyperadmin import Admin" runs
  Then  it exits 0

Scenario: dev-only packages are not runtime deps
  Given pyproject [project.dependencies]
  When  it is inspected
  Then  appnope, uvicorn and httpx are absent
  And   pydantic-settings is present
```

## Acceptance Criteria

- [ ] built wheel imports cleanly
- [ ] dev-only packages are not runtime deps
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)

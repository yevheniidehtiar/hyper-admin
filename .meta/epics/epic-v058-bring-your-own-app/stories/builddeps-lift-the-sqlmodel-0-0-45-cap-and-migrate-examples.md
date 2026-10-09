---
type: story
id: st-v058-byoa-48
title: "build(deps): lift the sqlmodel<0.0.45 cap and migrate examples and fixtures to utc_now"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:packaging
  - layer:ui
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Change `pyproject.toml` to `sqlmodel>=0.0.19`. Move `examples/simple/models.py:31,41` and the two test fixtures to `utc_now`. Run `poe deps:bump` across the 3-combination matrix and refresh the datetime visual baselines (never `--no-verify`).

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.10

## Files to Change

- `pyproject.toml`
- `uv.lock`
- `examples/simple/models.py`
- `tests/unit/test_introspection.py`
- `tests/unit/test_zero_config.py`
- `tests/e2e/__snapshots__`

## Scenarios

```
Scenario: lowest-direct green
  Given sqlmodel 0.0.19 on py3.10 lowest-direct
  When  poe lint and test:unit run
  Then  both pass

Scenario: highest green
  Given sqlmodel>=0.0.47 on py3.13 highest
  When  poe lint and test:unit run
  Then  both pass

Scenario: createsuperuser on new sqlmodel
  Given sqlmodel>=0.0.45 and built-in auth
  When  createsuperuser runs
  Then  the insert succeeds
```

## Acceptance Criteria

- [ ] lowest-direct green
- [ ] highest green
- [ ] createsuperuser on new sqlmodel
- [ ] `poe lint` and `poe test:unit` pass (and `poe test:e2e`)

## Blocked by

- `fixauth-tz-aware-auth-model-timestamps-via-utcnaivedatetime` (st-v058-byoa-16)
- `featforms-tz-aware-datetime-parsing-aware-naivedatetime-widg` (st-v058-byoa-32)
- `feattemplates-pk-agnostic-item-links-testids-and-tz-aware-da` (st-v058-byoa-45)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)

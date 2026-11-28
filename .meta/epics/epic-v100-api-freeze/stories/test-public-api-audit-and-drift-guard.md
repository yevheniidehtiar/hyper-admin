---
type: story
id: st-v100-freeze-03
title: "test(core): public API audit — every export documented, typed and covered"
status: done
priority: high
assignee: null
labels:
  - testing
  - size:M
  - planned
  - area:core
  - area:docs
estimate: null
epic_ref:
  id: ep-v100-freeze-01
created_at: 2026-11-20T00:00:00Z
updated_at: 2026-11-20T00:00:00Z
---

## Summary

Audit everything exported from `hyperadmin` (and the public names of its subpackages that the docs
reference): each name has a docstring, complete type annotations, a page or entry under `docs/api/` and
at least one test. Record the surface in a snapshot test so a later change to it is a deliberate diff.

## Files to Change

- **New:** `tests/unit/test_public_api.py` (snapshot of the exported names and their signatures)
- **Modified:** `docs/api/` pages for names that are missing
- **Modified:** docstrings and annotations of exports that lack them (no behaviour change)

## Scenarios

```
Scenario: an export is added without updating the snapshot
  Given the public API snapshot
  When  a new name is exported from hyperadmin
  Then  the snapshot test fails and names the new export

Scenario: a public signature changes
  Given the public API snapshot
  When  a parameter of an exported callable is renamed or removed
  Then  the snapshot test fails and shows the old and the new signature

Scenario: an export has no reference entry
  Given the list of exported names
  When  the docs reference is checked
  Then  every name is found under docs/api
```

## Acceptance Criteria

- [ ] an export is added without updating the snapshot
- [ ] a public signature changes
- [ ] an export has no reference entry
- [ ] Names that should not be public are listed for the owner instead of being removed
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `docs-versioning-and-deprecation-policy` (st-v100-freeze-01)

## Parent

- Epic: `epic-v100-api-freeze` (v1.0 — Stable Release)

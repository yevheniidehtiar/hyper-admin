---
type: story
id: st-conflict-06
title: "refactor(core): lazy one-line-per-symbol package exports with a drift guard"
status: todo
priority: low
assignee: null
labels:
  - size:S
  - planned
  - area:core
estimate: null
epic_ref:
  id: ep-conflict-avoidance-01
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

Package `__init__.py` files hold an import block plus a single-line `__all__ = [...]`, so two PRs that each export
one symbol edit the same line and conflict. Keep the public API explicit (CONSTITUTION §4) but make it merge-friendly:
each re-exporting `__init__.py` declares a `_LAZY_EXPORTS` mapping with **one symbol per line**, resolves it through
a PEP 562 `__getattr__`, and derives `__all__` from the mapping's keys. A unit test asserts that `__all__` matches the
mapping, that every entry resolves, and that `python -c "import hyperadmin"` does not import optional extras. Adding
an export becomes a one-line insert that only conflicts with a neighbour line, not with every other export.

`src/hyperadmin/auth/__init__.py` already uses lazy `__getattr__` (st-v058-byoa-17); align it to the same shape.

## Files to Change

- `src/hyperadmin/__init__.py`
- `src/hyperadmin/realtime/__init__.py`
- `src/hyperadmin/auth/__init__.py`
- `tests/unit/test_public_exports.py` (new)

## Scenarios

```
Scenario: Exports resolve lazily
  Given a fresh interpreter
  When  `import hyperadmin` runs
  Then  submodules behind lazy exports are not imported until accessed

Scenario: __all__ cannot drift
  Given a symbol added to _LAZY_EXPORTS
  When  the export test runs
  Then  __all__ contains it and `from hyperadmin import <symbol>` works

Scenario: Typos fail fast
  Given an unknown attribute
  When  `hyperadmin.<name>` is accessed
  Then  AttributeError is raised with the module name
```

## Acceptance Criteria

- [ ] Exports resolve lazily
- [ ] `__all__` cannot drift
- [ ] Typos fail fast
- [ ] mypy still sees the exported types (`TYPE_CHECKING` imports)
- [ ] 100 % coverage of changed lines; `poe lint` passes

## Blocked by

- v0.5.8 wave (owns `auth/**`; release story st-v058-byoa-50)

## Parent

- Epic: `epic-conflict-avoidance`

---
type: story
id: st-conflict-07
title: "refactor(core): route providers instead of hand-wired routes in core/app.py"
status: todo
priority: low
assignee: null
labels:
  - size:M
  - planned
  - area:core
estimate: null
epic_ref:
  id: ep-conflict-avoidance-01
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

`core/app.py` wires every feature's routes by hand (about 30 `include_router` / `add_api_route` / `mount` calls), so
every feature that adds an endpoint edits the same file. Add a small internal seam: a `RouteProvider` protocol
(`register(admin, router) -> None`) and an ordered provider list that `Admin` iterates at mount time. Each feature
module ships its own provider next to its views; `core/app.py` stops changing per feature. Ordering is explicit
(`order: int` on the provider, literal routes before parametrised ones) so route precedence stays deterministic.
This is a precursor to the public plugin registry (v0.8.0), not a replacement for it.

## Files to Change

- `src/hyperadmin/core/route_providers.py` (new) — protocol, ordering, built-in provider list
- `src/hyperadmin/core/app.py` — replace hand-wired calls with the provider loop
- `src/hyperadmin/routing.py` — move feature route registration into providers
- `tests/unit/test_route_providers.py` (new)

## Scenarios

```
Scenario: Route table is unchanged
  Given the built-in providers
  When  Admin mounts
  Then  the registered routes, names and order equal the pre-refactor table

Scenario: A feature adds routes without editing core/app.py
  Given a new provider registered from its own module
  When  Admin mounts
  Then  its routes are served

Scenario: Literal routes win over parametrised ones
  Given a provider with a literal path and one with a {pk} path at the same prefix
  When  the literal path is requested
  Then  the literal handler responds
```

## Acceptance Criteria

- [ ] Route table is unchanged (snapshot test of `app.routes`)
- [ ] A feature adds routes without editing core/app.py
- [ ] Literal routes win over parametrised ones
- [ ] 100 % coverage of changed lines; `poe lint` and `poe test:e2e` pass

## Blocked by

- v0.5.8 wave (owns `core/app.py` and `routing.py`; release story st-v058-byoa-50)

## Parent

- Epic: `epic-conflict-avoidance`

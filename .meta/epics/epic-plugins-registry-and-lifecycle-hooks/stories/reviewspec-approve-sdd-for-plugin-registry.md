---
type: story
id: NXipXCqMh_dL
title: "review(spec): approve SDD for plugin registry"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - plugins
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

**Human gate** — review and approve the SDD at `docs/specs/plugin-registry.md`.

## Checklist

- [ ] Problem statement is clear and scoped
- [ ] Goals are measurable (can be verified by acceptance criteria)
- [ ] Non-goals prevent over-engineering (explicit defer list)
- [ ] BDD scenarios cover happy path + ≥1 failure path (failure: hook raises)
- [ ] `Plugin` Protocol is backward compatible (no inheritance forced on plugins)
- [ ] Adapter wrapping doesn't break existing `BaseAdapter` contract
- [ ] Hook signatures are observer-only (no mutation in v1) — confirm
- [ ] No async hook support in v1 — confirm acceptable
- [ ] CLI subcommand pattern matches existing `createsuperuser`
- [ ] Backward compatible — no semver major bump required
- [ ] Open Questions resolved (`dispatch_hook` return values, async, naming, short-circuit)

## Open Questions to resolve at review

1. Should `dispatch_hook` allow handlers to return values (veto / mutate)?
2. Async hooks — defer to v0.8.1, or design from the start?
3. Naming: `on_before_adapter_call` vs `on_adapter_call_start` (recommend former).
4. Wrapper short-circuit: implicit in `dispatch` or explicit `has_handlers(name)`?

## Blocked by

- `docsspec-sdd-for-plugin-registry` (SDD draft committed)

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`

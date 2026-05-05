---
type: story
id: rJGg9GraxS4D
title: "docs(spec): SDD for plugin registry & lifecycle hooks"
status: done
priority: high
assignee: null
labels:
  - documentation
  - size:S
  - planned
  - plugins
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Write the Software Design Document for the Plugin Registry & Lifecycle Hooks epic.

**Output:** `docs/specs/plugin-registry.md` (Status: Draft)

## Scope

The SDD must cover:
- `Plugin` protocol design (runtime-checkable, optional hook methods, `name` attribute)
- `PluginRegistry` design — discovery via `importlib.metadata.entry_points`, disable
  mechanism (ctor + env var), failure isolation
- App-level hook list and signatures (`on_model_register`, `on_before_create`,
  `on_after_create`, `on_before_update`, `on_after_update`, `on_before_delete`,
  `on_after_delete`, `on_before_adapter_call`, `on_after_adapter_call`)
- Adapter wrapping strategy (decided: wrap at `SiteRegistry.register()` boundary)
- Edge cases: import failures, hook exceptions, name collisions, async hooks (deferred)
- Backward compatibility: pure addition, no semver major bump
- Decision log entries with rejected alternatives

## Acceptance Criteria

- [x] SDD follows `docs/specs/TEMPLATE.md` structure
- [x] BDD scenarios synced with epic body
- [x] Status set to "Draft"
- [x] Adapter wrapping strategy decided and recorded in Decision Log
- [x] Open Questions enumerated for review

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`

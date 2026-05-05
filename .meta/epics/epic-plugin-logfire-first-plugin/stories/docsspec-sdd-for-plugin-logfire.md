---
type: story
id: knE8pAvm9TB7
title: "docs(spec): SDD for hyperadmin-logfire plugin"
status: done
priority: high
assignee: null
labels:
  - documentation
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

Write the Software Design Document for the `hyperadmin-logfire` plugin epic.

**Output:** `docs/specs/plugin-logfire.md` (Status: Draft)

## Scope

The SDD must cover:
- Repo layout decision: monorepo subpath vs separate repo (decided: monorepo subpath)
- `instrument_admin(admin)` API surface and idempotency
- Hook usage table — which Epic 1 hooks are consumed, which are net-new
- Span context propagation between `on_before_adapter_call` / `on_after_adapter_call`
  using `contextvars`
- Failure modes: `logfire` not configured, not installed, double-instrument
- CI: workspace `pyproject.toml` integration, separate test matrix entry
- PyPI publication strategy (separate package, optional `hyperadmin[logfire]` extra)
- Decision log entries with rejected alternatives

## Acceptance Criteria

- [x] SDD follows `docs/specs/TEMPLATE.md` structure
- [x] BDD scenarios synced with epic body
- [x] Status set to "Draft"
- [x] Repo layout decision recorded
- [x] Hook dependency on Epic 1 SDD made explicit (two new hooks listed)
- [x] Open Questions enumerated for review

## Parent

- Epic: `epic-plugin-logfire-first-plugin`

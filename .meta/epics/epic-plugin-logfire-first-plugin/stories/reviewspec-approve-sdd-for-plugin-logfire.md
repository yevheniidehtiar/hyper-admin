---
type: story
id: ZmEtqRqTuUZE
title: "review(spec): approve SDD for hyperadmin-logfire"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - plugins
  - observability
estimate: null
epic_ref:
  id: Plo-enMpTWhB
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

**Human gate** — review and approve the SDD at `docs/specs/plugin-logfire.md`.

## Checklist

- [ ] Problem statement and goals are clear
- [ ] Non-goals prevent over-engineering (dashboard widget, OTel-generic deferred)
- [ ] BDD scenarios cover happy path + ≥1 failure path (logfire-not-configured)
- [ ] Repo layout decision is sound (monorepo subpath)
- [ ] Hook dependency on Epic 1 is explicit (two new hooks listed)
- [ ] No core changes required beyond the new hooks
- [ ] `instrument_admin` is idempotent and degrades gracefully
- [ ] PyPI publishing strategy is acceptable (separate package, optional extra)
- [ ] Open Questions resolved

## Open Questions to resolve at review

1. Add `[project.optional-dependencies].logfire = ["hyperadmin-logfire>=0.1"]` to root?
2. Span name convention: `admin.adapter.list` vs `hyperadmin.adapter.list` (recommend former).
3. Include `logfire.instrument_pydantic()`? (recommend no — too noisy)
4. Verify Logfire test sink fixture works under our pytest-asyncio setup.

## Blocked by

- `docsspec-sdd-for-plugin-logfire` (SDD draft committed)
- `reviewspec-approve-sdd-for-plugin-registry` (Epic 1 SDD must be approved with the
  two new hooks `on_validation_error` and `on_auth_event` added)

## Parent

- Epic: `epic-plugin-logfire-first-plugin`

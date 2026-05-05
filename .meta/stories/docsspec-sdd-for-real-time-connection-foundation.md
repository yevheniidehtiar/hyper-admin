---
type: story
title: "docs(spec): SDD for real-time connection foundation"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - agent-task
  - size:M
  - area:realtime
estimate: null
epic_ref: null
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Context
Epic 6.2.1 is `size:L` and touches ≥ 2 modules (`realtime/` (new), `core/app.py`, `templates/`, `static/`). Per `.claude/rules/sdd-conventions.md` an approved SDD is required before implementation begins.

## Acceptance Criteria
- [ ] `docs/specs/realtime-connection-foundation.md` created using `docs/specs/TEMPLATE.md`
- [ ] Status: Draft → In Review → Approved (human gate)
- [ ] BDD scenarios from the implementation stories pasted into the SDD `## BDD Scenarios` section
- [ ] Architecture section names every new file under `src/hyperadmin/realtime/` and the `Admin.mount()` wiring point
- [ ] Edge-case table covers: idle proxy timeout, reload-cycle leak, reconnect storm, auth bypass on WS scope, server-shutdown drain
- [ ] Decision Log records: SSE + WS (vs one transport), `ConnectionRegistry` (no PubSub), in-memory only (Redis deferred), opt-in via `realtime` kwarg

## Files Likely Affected
- `docs/specs/realtime-connection-foundation.md` (new)

## Dependencies
Blocks every implementation story in the MVP slice.

## Notes for Implementer
Re-use the BDD scenarios verbatim from the test/feat stories so the issue body and SDD never drift. Once approved, implementation sub-tasks unblock.

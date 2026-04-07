---
type: story
id: MiyBvGJCR6aP
title: "feat(presence): PresenceBackend protocol + InMemoryPresence implementation"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:presence
estimate: null
epic_ref:
  id: Y-nzspSqDFUM
github:
  issue_number: 323
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:67bd99368f2c7e0c7c2033dc1e3600daa720d4dea758c71191d3a0aa03ea970d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:01:03Z
updated_at: 2026-03-29T07:01:03Z
---

## Context
Defines the PresenceBackend protocol and ships the default in-memory implementation with asyncio-based TTL expiry.

## Acceptance Criteria
- [ ] `src/hyperadmin/core/presence.py` created with `PresenceBackend` Protocol and `PresenceEntry` dataclass
- [ ] `src/hyperadmin/adapters/presence/__init__.py` and `memory.py` created
- [ ] `InMemoryPresence` uses asyncio tasks for TTL cleanup
- [ ] All P1 tests pass
- [ ] `PresenceEntry` has: `user_id: str`, `display_name: str`, `mode: Literal["viewing", "editing"]`, `since: datetime`

## Files Likely Affected
- `src/hyperadmin/core/presence.py` (new)
- `src/hyperadmin/adapters/presence/__init__.py` (new)
- `src/hyperadmin/adapters/presence/memory.py` (new)

## Dependencies
Depends on: #322

## Notes for Implementer
Follow same pattern as `core/realtime.py` + `adapters/pubsub/memory.py`. TTL cleanup via `asyncio.create_task(asyncio.sleep(ttl))` then remove entry.

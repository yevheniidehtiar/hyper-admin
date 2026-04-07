---
type: story
id: hscJiAdjrTEU
title: "feat(realtime): PubSubBackend protocol + InMemoryPubSub implementation"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 303
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:2814541ccb9b463c117b9dfefd85032691c3dcf6d433cc42de0938e45030df75
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:57:52Z
updated_at: 2026-03-29T06:57:52Z
---

## Context
Defines the core PubSubBackend Protocol and ships the zero-config InMemoryPubSub. This is the foundation all notification and presence features build on.

## Acceptance Criteria
- [ ] `src/hyperadmin/core/realtime.py` created with `PubSubBackend` Protocol (publish, subscribe→AsyncIterator[bytes], unsubscribe, close)
- [ ] `src/hyperadmin/adapters/pubsub/__init__.py` and `memory.py` created
- [ ] `InMemoryPubSub` uses `asyncio.Queue` per channel
- [ ] All tests from T1 pass
- [ ] No changes to existing public API surface

## Files Likely Affected
- `src/hyperadmin/core/realtime.py` (new)
- `src/hyperadmin/adapters/pubsub/__init__.py` (new)
- `src/hyperadmin/adapters/pubsub/memory.py` (new)

## Dependencies
Depends on: #302

## Notes for Implementer
Follow CONSTITUTION.md: `core/` defines protocols only — no concrete implementations. Concrete impl goes in `adapters/pubsub/`. Dependency direction: adapters → core, never reverse.

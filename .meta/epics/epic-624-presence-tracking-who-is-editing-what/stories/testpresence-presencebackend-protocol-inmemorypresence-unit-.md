---
type: story
id: X0tH_LblgJPQ
title: "test(presence): PresenceBackend protocol + InMemoryPresence unit tests"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - size:S
  - area:presence
estimate: null
epic_ref:
  id: Y-nzspSqDFUM
github:
  issue_number: 322
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:18dfb4a4aacb6037ec6ee0a5c9fcc90ec8ad29dd0988e3e706f48e30475d9938
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:00:52Z
updated_at: 2026-03-29T07:00:52Z
---

## Context
Presence tracking tells admins who else is viewing or editing the same record, preventing duplicate work and accidental overwrites. InMemoryPresence is the zero-config default.

## Acceptance Criteria
- [ ] Test: `set_presence(channel, user_id, data, ttl)` stores entry
- [ ] Test: `get_presence(channel)` returns list of `PresenceEntry`
- [ ] Test: `remove_presence(channel, user_id)` removes entry
- [ ] Test: TTL expiry — entry not returned after TTL seconds
- [ ] Test: channel isolation — presence in ch-A not visible in ch-B
- [ ] Tests in `tests/unit/test_presence_memory.py`

## Files Likely Affected
- `tests/unit/test_presence_memory.py` (new)

## Dependencies
None — first task in Track C. Note: Track C requires T6 (ConnectionManager) from v0.6.2 to be merged before P5.

## Notes for Implementer
Tests must FAIL before P2. Can be worked in parallel with v0.6.2 tasks.

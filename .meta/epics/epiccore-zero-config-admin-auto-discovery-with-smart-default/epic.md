---
type: epic
id: QqLkPxnNHcRm
title: "epic(core): Zero-Config Admin — Auto-Discovery with Smart Defaults"
status: done
priority: medium
owner: null
labels:
  - auto-discovery
  - agent-task
  - area:core
milestone_ref:
  id: WUIXeOSj83Kt
github:
  issue_number: 382
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:be8b50588c6b919f17f1eb70c7d5876558f8e1382e24902f3cd37f58eafe0a8e
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T09:11:39Z
updated_at: 2026-04-01T09:24:26Z
---

## Overview

Mount HyperAdmin in 3 lines of code. Auto-detect all SQLModel models, infer list_display/search_fields/list_filter from field types, display human-readable labels. Explicit registrations override auto-detected defaults.

## Tasks

- [ ] #363 — feat(core): model introspection utility for field metadata
- [ ] #364 — feat(core): smart defaults — infer list_display
- [ ] #365 — feat(core): smart defaults — infer search_fields
- [ ] #366 — feat(core): smart defaults — infer list_filter
- [ ] #367 — feat(core): auto-discovery — scan SQLModel metadata
- [ ] #368 — feat(core): extend AdminOptions to support None for smart defaults
- [ ] #369 — feat(views): display inferred field labels in list/detail views
- [ ] #370 — feat(core): auto-register discovered models with smart defaults
- [ ] #371 — feat(core): add auto_discover parameter to Admin()
- [ ] #372 — test: 3-line zero-config demo verification
- [ ] #373 — test(e2e): zero-config auto-discovery with mixed models

## Dependency Graph

```
#363 ──┬→ #364 ─┐
       ├→ #365 ─┤
       ├→ #366 ─┼→ #370 → #371 ─┬→ #372
       ├→ #367 ─┘                │
       ├→ #368                   └→ #373
       └→ #369
```

## Parallel Tracks

#363 is the foundation — all others depend on it.
#364, #365, #366, #367, #368, #369 can proceed in parallel after #363.
#370 requires #364+#365+#366+#367.
#371 requires #370.
#372 requires #370+#371.
#373 requires all above.

---
type: story
id: Lw6vtSrWcVBp
title: "chore: add priority labels to all open issues"
status: todo
priority: medium
assignee: null
labels:
  - gitpm
  - maintenance
estimate: null
epic_ref: null
github:
  issue_number: 492
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8b080994aee475eb680959f7f3fba5e3f75a35464689e27dcb848a9c8164a1a5
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-05T09:50:22Z
updated_at: 2026-04-05T09:50:22Z
---

## Problem
After GitPM import, all 342 stories show `priority: medium` because no GitHub priority labels exist.

## Solution
1. Create GitHub labels: `priority:critical`, `priority:high`, `priority:medium`, `priority:low`
2. Apply labels to all open issues based on milestone urgency and feature importance
3. Re-sync with GitPM to populate the priority field correctly

## Priority Guidelines
- **critical**: Blocks other work, security issues, data loss bugs
- **high**: Current milestone features, user-facing bugs
- **medium**: Next milestone features, technical debt
- **low**: Nice-to-have, cosmetic, future ideas

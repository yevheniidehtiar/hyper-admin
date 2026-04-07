---
type: story
id: 6sCxAqjz9bSj
title: "chore: triage 179 stale todo issues — close obsolete, prioritize active"
status: todo
priority: medium
assignee: null
labels:
  - gitpm
  - maintenance
estimate: null
epic_ref: null
github:
  issue_number: 491
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7219337d2f59c96e91c80dfd4b5ddf97248cfdedae8366bf8b310cfe7128121c
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-05T09:50:22Z
updated_at: 2026-04-05T09:50:22Z
---

## Problem
After GitPM migration, analysis reveals:
- **179 issues** in `todo` status (49% of all issues)
- **167 issues** in `done` status
- **15 issues** in `in_progress`
- **ALL 342 stories** have `priority: medium` — no prioritization exists

Many of the 179 todos were created months ago and may be:
- Superseded by later work
- Duplicates of other issues
- No longer relevant to the project direction

## Proposed Action
1. Review each milestone's todo issues
2. Close issues that are obsolete or won't be done
3. Add actual priority labels (`priority:high`, `priority:low`) to remaining issues
4. Re-sync with GitPM to update .meta files

## Milestones to Review (by todo count)
Focus on milestones with the most open issues first.

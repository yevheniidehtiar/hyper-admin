---
type: story
id: 10AXkENiLUfB
title: "chore: link 195 orphan stories to their parent epics"
status: todo
priority: medium
assignee: null
labels:
  - gitpm
  - maintenance
estimate: null
epic_ref: null
github:
  issue_number: 493
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:acf6196704f3917a3d48cbd72374b5a59354b91149a4ebbffe2db7291dcd4b39
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-05T09:50:23Z
updated_at: 2026-04-05T09:50:23Z
---

## Problem
GitPM import linked only 35% of stories to epics (106/301). The remaining 195 stories sit in `.meta/stories/` without any epic reference, making them hard to discover and manage.

## Root Cause
Many stories reference epics via milestone grouping or labels (`area:core`, `area:adapters`) rather than body text `#N` references.

## Solution
1. For each orphan story, identify the correct parent epic by:
   - Checking which milestone/epic shares the same labels
   - Reading the body for context clues
   - Matching against epic sub-issue lists
2. Add `epic_ref` to each story's frontmatter
3. Move files from `.meta/stories/` to `.meta/epics/<epic-name>/stories/`
4. Re-validate with `gitpm validate`

## Impact
Without epic grouping, the project tree is a flat list of 301 items — unusable for planning.

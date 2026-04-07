---
type: story
id: OvZ4f6_PqV9o
title: "fix: remove github-state.json from .gitignore to preserve sync state"
status: todo
priority: medium
assignee: null
labels:
  - gitpm
estimate: null
epic_ref: null
github:
  issue_number: 490
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ce332c8f831cca604be7852e73020b852c8fd984350db79e2a14b787ab7acb33
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-05T09:50:22Z
updated_at: 2026-04-05T09:50:22Z
---

## Problem
PR #489 added `.meta/sync/github-state.json` to `.gitignore`. This means:
- Fresh clones lose all sync state
- GitPM sync dashboard shows 'Not Synced / Never' for all 362 entities
- Re-syncing would create duplicates or fail to match entities

## Solution
Remove the gitignore entry. The sync state file is small (~30KB) and should be versioned alongside the .meta tree. It contains content hashes and GitHub issue numbers needed for bidirectional sync.

## Steps
1. Remove `.meta/sync/github-state.json` from `.gitignore`
2. Re-run `gitpm import` to regenerate the state file
3. Commit and push

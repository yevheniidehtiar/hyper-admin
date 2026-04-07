---
type: story
id: 5oGyVyVG70wn
title: "chore: add explicit sub-issue references (#N) to all epic bodies"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - maintenance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
github:
  issue_number: 494
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:48a3977e2a08d573b99da070dc1eca85db6183d923e5b7582015d5fa0a2b13d1
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-05T09:50:23Z
updated_at: 2026-04-05T09:50:23Z
---

## Problem
Some epics have detailed sub-issue lists in their body (e.g. #211 adapter query perf), but many don't. This means GitPM can't auto-link stories to epics during future re-imports.

## Solution
For each epic, add a '## Sub-issues' section listing all child stories:
```markdown
## Sub-issues
- #123 feat: implement X
- #124 test: unit tests for X
- #125 docs: document X
```

This makes the epic self-documenting AND enables GitPM to auto-link on import.

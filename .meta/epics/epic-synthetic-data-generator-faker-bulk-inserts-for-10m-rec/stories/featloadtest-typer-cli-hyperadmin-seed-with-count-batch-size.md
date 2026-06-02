---
type: story
id: kanghFUxVhWJ
title: "feat(loadtest): Typer CLI hyperadmin seed with --count, --batch-size, --database-url"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - size:M
  - performance
  - area:cli
  - area:loadtest
estimate: null
epic_ref:
  id: SnjolGjNN_F7
github:
  issue_number: 254
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:32723b9be196185fc0a95005b9e8aad8cdbe9b3c17dafcd820013e3c2bbd4e7c
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:06:56Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #246 (E: Synthetic Data Generator).
Follows the existing `hyperadmin createsuperuser` CLI pattern.

## Acceptance criteria
- [ ] `hyperadmin seed --count 1000000 --batch-size 5000 --database-url postgresql+asyncpg://...` works
- [ ] Defaults: count=1000, batch_size=5000, database_url from env or SQLite fallback
- [ ] Registers as Typer subcommand in `__main__.py`
- [ ] Detects SQLite vs PostgreSQL and adjusts batch strategy
- [ ] Shows progress bar during seeding
- [ ] Supports both SQLite and PostgreSQL database URLs

## Files
- `src/hyperadmin/management/commands/seed.py` (new)
- `src/hyperadmin/__main__.py` (modify: register subcommand)

## Dependencies
- Blocked by: #249 (E2 seeder), #251 (E4 FK pool)
- Blocking: E8, F9

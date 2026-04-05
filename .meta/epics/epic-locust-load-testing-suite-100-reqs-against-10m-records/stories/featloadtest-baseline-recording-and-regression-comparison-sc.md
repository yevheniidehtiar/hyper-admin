---
type: story
id: sX8rX9sJOSb0
title: "feat(loadtest): baseline recording and regression comparison script"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - agent:claude
  - size:M
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: 7OiB1iArrAfF
github:
  issue_number: 263
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:35157b2d0fce1b6c64283c7efd9a00e9b00c8279af5019b2afd07feeb897652d
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T01:08:44Z
updated_at: 2026-03-27T01:08:44Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).

## Acceptance criteria
- [ ] Parse Locust CSV/JSON stats output into structured baseline format
- [ ] Save baseline as JSON to `loadtest/baselines/baseline.json`
- [ ] Compare subsequent run against baseline: per-endpoint p50, p95, p99, throughput, error rate
- [ ] Exit code 1 if regression detected: p95 > 2× baseline OR error rate > 1%
- [ ] Human-readable comparison table printed to stdout
- [ ] `--update-baseline` flag to overwrite existing baseline

## Files
- `examples/erp/loadtest/baselines.py` (new)

## Dependencies
- Blocked by: #261 (F5 read users), #262 (F6 write users)
- Blocking: F9

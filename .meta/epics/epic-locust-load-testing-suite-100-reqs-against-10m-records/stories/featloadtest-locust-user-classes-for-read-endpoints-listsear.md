---
type: story
id: X_6YZRlfUxh_
title: "feat(loadtest): Locust user classes for read endpoints (list/search/sort/detail/choices)"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - agent:claude
  - size:L
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: 7OiB1iArrAfF
github:
  issue_number: 261
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:65048e242e86e4991e71da1a2e5c7d9aeeaadde6f517bee43b2c1fc8e7e46f84
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T01:08:25Z
updated_at: 2026-03-27T01:08:25Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).

## Acceptance criteria
- [ ] `ReadUser` class inherits from `HyperAdminAuthMixin` + `HttpUser`
- [ ] Weighted tasks: list (40%), search (15%), sort (10%), detail (15%), choices (10%)
- [ ] Parametrized URLs: random page numbers (1-1000), random search terms from Faker, random sort fields
- [ ] Random model selection across Contact, Invoice, JournalLine
- [ ] Validates response status codes (200 OK expected)
- [ ] All tests from F4 pass

## Files
- `examples/erp/loadtest/locustfile.py` (new)

## Dependencies
- Blocked by: #259 (F3 auth mixin), #260 (F4 tests)
- Blocking: F6, F7

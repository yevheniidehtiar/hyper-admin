---
type: story
id: u9mZSvAnXpD8
title: "test: unit tests for Admin show_banner and CLI --quiet flag"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - size:XL
estimate: null
epic_ref: null
github:
  issue_number: 286
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3332d54556c785b1f6017b6d3b27584fb14b459c8bb4d364984838415ecaaf99
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T23:06:42Z
updated_at: 2026-03-27T23:23:51Z
---

## Context
Following TDD rules (testing.md), unit tests must cover the new `show_banner` parameter on Admin
and the `--quiet` CLI flag to ensure correctness, prevent regressions, and reach near-99% coverage
on the changed files.

## Acceptance Criteria
- [ ] Unit test: `Admin(show_banner=True)` prints banner to stdout on startup
- [ ] Unit test: `Admin(show_banner=False)` produces no stdout output on startup
- [ ] Unit test: CLI `--quiet` flag invokes Admin with `show_banner=False`
- [ ] Unit test: CLI without `--quiet` invokes Admin with `show_banner=True` (default)
- [ ] All tests pass under `poe test:unit`
- [ ] Coverage on `core/app.py` and `__main__.py` remains near 99%

## Files Likely Affected
- `tests/unit/test_admin_banner.py` (new file)
- `tests/unit/test_cli.py` (new or existing)

## Dependencies
Depends on: #283, #284

## Notes for Implementer
- Use `capsys` pytest fixture to assert stdout content (or absence thereof)
- Mock or patch the Admin startup event for unit isolation — do not spin up a real server
- testing.md: TDD approach — write failing tests first, implement to pass, then refactor

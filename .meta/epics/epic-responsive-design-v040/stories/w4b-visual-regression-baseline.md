---
type: story
id: Fm1NkN9kfAW1
title: "test(e2e): visual regression screenshot baseline for responsive"
status: todo
priority: low
assignee: null
labels:
  - frontend
  - testing
  - size:S
  - responsive
  - cycle:3-stagger
estimate: null
epic_ref:
  id: cvr4sYoEN9CV
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Summary

Create Playwright screenshot baseline snapshots at three breakpoints (375px, 768px, 1024px)
for list, create, detail, and login views. These serve as a visual regression safety net.

## Scenarios

**Scenario: screenshot baseline captured at mobile viewport**
  Given viewport width is 375px
  When  the list view loads
  Then  a screenshot is captured and matches the baseline

**Scenario: screenshot baseline captured at desktop viewport**
  Given viewport width is 1024px
  When  the list view loads
  Then  a screenshot is captured and matches the baseline

## Acceptance criteria

- [ ] Screenshot baselines exist for 375px, 768px, 1024px
- [ ] Covers list, create, detail, login views
- [ ] CI can compare against baselines

## Files to modify

- `tests/e2e/test_visual_regression.py` — new test file

## Demo checkpoint

Run `poe test:e2e -- tests/e2e/test_visual_regression.py --update-snapshots` to generate baselines.

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** C3-B (B57RGgp05uU0) — needs E2E test suite for screenshot baseline

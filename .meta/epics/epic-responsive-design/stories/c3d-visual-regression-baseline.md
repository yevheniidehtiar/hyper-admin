---
type: story
id: RspSyn_C3D_01
title: "test(e2e): visual regression screenshot baseline for responsive"
status: todo
priority: low
assignee: null
labels:
  - frontend
  - testing
  - size:S
  - responsive
  - cycle:3
estimate: null
epic_ref:
  id: RspSynth_01
github: null
created_at: 2026-04-08T00:00:00Z
updated_at: 2026-04-08T00:00:00Z
---

## Summary

Create Playwright screenshot baseline snapshots at three breakpoints (375px, 768px, 1024px)
for list, create, detail, and login views. These serve as a visual regression safety net
for future CSS changes.

Cherry-picked from Beta PPU experiment.

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

## Files to create

- `tests/e2e/test_visual_regression.py` -- Playwright visual regression tests

## Demo checkpoint

Run `poe test:e2e -- tests/e2e/test_visual_regression.py --update-snapshots` to generate baselines.

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** C3-C (E2E responsive test suite)

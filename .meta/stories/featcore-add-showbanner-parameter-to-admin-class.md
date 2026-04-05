---
type: story
id: JSaabK2xfZGi
title: "feat(core): add show_banner parameter to Admin class"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - in-progress
  - agent-task
  - size:XL
estimate: null
epic_ref: null
github:
  issue_number: 283
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:2dfc2c64bc3759ed31ea0e2130d610cf1416794ed36cf7bd84b8839e7e03b260
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T23:05:46Z
updated_at: 2026-03-27T23:36:33Z
---

## Context
The Admin class (src/hyperadmin/core/app.py) currently always outputs a startup banner to stdout
when the application starts. To support suppression via a --quiet CLI flag, we need to introduce
a `show_banner: bool = True` constructor parameter that controls whether the banner is printed
during the startup lifecycle.

## Acceptance Criteria
- [ ] `Admin.__init__` accepts a `show_banner: bool = True` parameter
- [ ] When `show_banner=False`, no banner text is printed to stdout during startup
- [ ] When `show_banner=True` (default), existing banner behavior is preserved
- [ ] Type hints are complete and mypy-clean
- [ ] No changes to views/, adapters/, or routing layer required

## Files Likely Affected
- `src/hyperadmin/core/app.py`

## Dependencies
None — this is the foundational layer change.

## Notes for Implementer
- Per CONSTITUTION.md §1: `core/` must not import from `views/` or `adapters/`
- Follow code-style.md: type hints required on all functions, line length 100 chars
- The banner print should be a simple `print()` call guarded by `if self.show_banner:`
- Keep the default `show_banner=True` so existing users are unaffected

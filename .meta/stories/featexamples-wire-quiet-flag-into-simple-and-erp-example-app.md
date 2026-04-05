---
type: story
id: r-O9SqF-T-Hn
title: "feat(examples): wire --quiet flag into simple and erp example apps"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:XL
estimate: null
epic_ref: null
github:
  issue_number: 285
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:4519dcadc088e2a4daff623dbfb46a74c3b095561f87e7200299490b4e77484c
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T23:06:18Z
updated_at: 2026-03-27T23:23:50Z
---

## Context
The example apps (`examples/simple/main.py` and `examples/erp/main.py`) are the reference
implementations that demonstrate HyperAdmin usage. They need to be updated to accept and
forward the `--quiet` flag to the `Admin` constructor so the examples remain consistent with
the new CLI feature.

## Acceptance Criteria
- [ ] `examples/simple/main.py` passes `show_banner` through to `Admin(...)` when applicable
- [ ] `examples/erp/main.py` passes `show_banner` through to `Admin(...)` when applicable
- [ ] Running `python -m hyperadmin ... --quiet` against either example suppresses the banner
- [ ] No banner suppression regression: default behavior (banner shown) is preserved

## Files Likely Affected
- `examples/simple/main.py`
- `examples/erp/main.py`

## Dependencies
Depends on: #283, #284

## Notes for Implementer
- Examples should remain minimal and readable — do not add argparse/click/typer directly
  to the example files; the flag should flow from the CLI layer (#284) into Admin construction
- Follow existing patterns in examples: keep startup logic in the lifespan context manager

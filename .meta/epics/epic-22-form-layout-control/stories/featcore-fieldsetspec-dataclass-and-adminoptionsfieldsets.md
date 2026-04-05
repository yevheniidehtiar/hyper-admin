---
type: story
id: lMY5iMOasXCi
title: "feat(core): FieldsetSpec dataclass and AdminOptions.fieldsets"
status: done
priority: medium
assignee: null
labels:
  - in-progress
  - jules
  - agent-task
  - area:core
  - size:S
estimate: null
epic_ref:
  id: HMxZRjunTlAA
github:
  issue_number: 188
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5da46a0ad3ed17174fcdb2a66b32d8b35701ba3cd5467f0d68ebc7b60bad0c2d
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:34:38Z
updated_at: 2026-03-28T19:45:57Z
---

> **Part of:** #38
> **No dependencies (base task)**

## Acceptance Criteria
- [ ] `core/options.py`: `FieldsetSpec(title: str, fields: list[str], collapsible: bool = False)` dataclass
- [ ] `AdminOptions` updated to accept `fieldsets: list[FieldsetSpec] | None = None`
- [ ] Exported from `core/__init__.py`
- [ ] No imports from `views/` or `adapters/`
- [ ] `mypy` clean

## Files
- `src/hyperadmin/core/options.py`
- `src/hyperadmin/core/__init__.py`


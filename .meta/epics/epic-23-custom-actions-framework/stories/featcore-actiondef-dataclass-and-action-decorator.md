---
type: story
id: qoCU_rqHfvNE
title: "feat(core): ActionDef dataclass and @action decorator"
status: done
priority: medium
assignee: null
labels:
  - in-progress
  - jules
  - agent-task
  - area:core
  - size:M
estimate: null
epic_ref:
  id: kR3DYwg4B6e2
github:
  issue_number: 184
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:75274c4f822f0009a0282a46b614ea54f29fb31bd4baadf6d7df5b1cf7e810aa
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-25T13:34:10Z
updated_at: 2026-03-28T19:44:39Z
---

> **Part of:** #41
> **No dependencies (base task)**

## Acceptance Criteria
- [ ] `src/hyperadmin/core/actions.py` (new): `ActionDef(name, label, handler, requires_selection=False)` dataclass
- [ ] `@action(label=...)` decorator registers an `ActionDef` on a `ModelView` class
- [ ] Exported from `core/__init__.py`
- [ ] No imports from `views/` or `adapters/`
- [ ] `mypy` clean

## Files
- `src/hyperadmin/core/actions.py` (new)
- `src/hyperadmin/core/__init__.py`


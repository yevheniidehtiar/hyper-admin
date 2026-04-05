---
type: story
id: Sc65kNuWLQu8
title: "feat(core): define ChoicesProvider protocol and SelectFieldMeta"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - jules
  - agent-task
estimate: null
epic_ref: null
github:
  issue_number: 160
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f1b5d701ed72edb78866f5b42fe9253cc155081b28479a7be6d23637b966af20
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-20T15:36:11Z
updated_at: 2026-03-21T00:09:56Z
---

## Context

Before any widget or adapter can serve choices, the system needs a typed contract that describes:
- how choices are provided (sync static list, async paginated query)
- what metadata a field carries to hint the widget layer (choices source, preload strategy, search enabled)

This is the foundational contract that all other issues in the epic depend on.

## Acceptance Criteria

- [ ] `ChoicesProvider` protocol defined in `core/adapters.py` (or `core/choices.py` if it stays small) with:
  - `async def get_choices(field: str, q: str = "", limit: int = 50, offset: int = 0, **filters) -> list[ChoiceItem]`
  - `ChoiceItem` typed dict/dataclass: `{value: str, label: str, selected: bool}`
- [ ] `SelectFieldMeta` dataclass or TypedDict carrying widget hints:
  - `choices_source: Literal["enum", "static", "relation"]`
  - `preload: bool` (True = all choices baked into page; False = HTMX lazy)
  - `multiple: bool`
  - `searchable: bool`
  - `dependent_on: str | None` (field name this select filters by)
- [ ] Exported from `core/__init__.py`
- [ ] Type-check clean (`mypy --strict`)
- [ ] Unit tests covering protocol shape and dataclass defaults

## Files Likely Affected

- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/core/__init__.py`
- `tests/unit/test_core_choices.py` (new)

## Dependencies

— (no dependencies, this is the base)

## Notes for Implementer

Keep this strictly in `core/` — no ORM imports. Per CONSTITUTION.md, `core/` must not depend on `adapters/` or `views/`.
`ChoiceItem` should be serialisable to JSON for the HTMX endpoints downstream.

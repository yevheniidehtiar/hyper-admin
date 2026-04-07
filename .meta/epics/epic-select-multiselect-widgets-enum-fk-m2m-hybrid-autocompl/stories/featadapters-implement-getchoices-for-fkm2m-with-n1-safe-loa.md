---
type: story
id: LVWK69ue_LPz
title: "feat(adapters): implement get_choices() for FK/M2M with N+1-safe loading"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
estimate: null
epic_ref:
  id: -TGq_yaQZtX_
github:
  issue_number: 161
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ccaec743834e368c33b59807d01f4a068132b34b0f831f7ab902d712c932af7a
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-20T15:36:33Z
updated_at: 2026-03-26T23:51:13Z
---

> **Part of:** #159
> **Depends on: #160**

## Context

The adapter layer must expose paginated, searchable choice lists for FK and M2M fields.
This is the DB-facing implementation of the `ChoicesProvider` protocol from #160.
N+1 safety is a hard requirement — all relationship traversals must use `selectinload` or equivalent.

## Acceptance Criteria

- [ ] `SQLModelAdapter` implements `ChoicesProvider.get_choices()`:
  - FK fields: single `SELECT` with optional `WHERE label ILIKE %q%`, paginated via `LIMIT/OFFSET`
  - M2M fields: single join query, no per-row fetches
  - Returns `list[ChoiceItem]` — never raw ORM objects
- [ ] `SQLAlchemyAdapter` implements the same interface
- [ ] `get_choices()` accepts `**filters` for dependent/cascading support (e.g. `country_id=3`)
- [ ] No N+1: verified by asserting `SELECT` count in unit tests (use `sqlalchemy.event` or query counter fixture)
- [ ] `preload` flag respected: when `preload=True`, all choices fetched at form-render time via `selectinload`
- [ ] Pagination: `limit` default 50, max 200 (reject larger, raise `ValueError`)

## Files Likely Affected

- `src/hyperadmin/adapters/sqlmodel.py`
- `src/hyperadmin/adapters/sqlalchemy.py`
- `src/hyperadmin/core/adapters.py` (add method to BaseAdapter protocol)
- `tests/unit/test_adapter_choices.py` (new)

## Dependencies

Depends on: #160

## Notes for Implementer

Use `inspect(model_class).relationships` (SQLAlchemy mapper inspection) to detect M2M vs FK.
For M2M the join table is implicit; use `joinedload` or `selectinload` — never `lazyload`.
The `label` for each choice should call `str(record)` on the related model instance — the user registers `__str__` on their models.
String search should be case-insensitive and applied to the `__str__` representation or a configurable `search_fields` list on the model.

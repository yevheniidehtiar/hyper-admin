---
type: story
id: VMx51BchLonI
title: "feat(core): extend AdminOptions to support None for smart defaults"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 368
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a4a324470fc0ad450ec68feafc029624092ed4823abfd03e9c37959dafb3a864
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T08:52:07Z
updated_at: 2026-03-31T20:43:35Z
---

## Context

`AdminOptions.list_display` and `AdminOptions.search_fields` currently default to `[]`. Change to `list[str] | None = None` where `None` triggers smart defaults and explicit `[]` means "show nothing / disable search".

## Scenarios

**Scenario: None triggers smart defaults**
  Given `AdminOptions(list_display=None)`
  When  the list view resolves columns
  Then  `infer_list_display()` is called to determine columns

**Scenario: explicit empty list disables feature**
  Given `AdminOptions(list_display=[])`
  When  the list view resolves columns
  Then  no columns are shown (no inference)

**Scenario: explicit list is used as-is**
  Given `AdminOptions(list_display=["id", "name"])`
  When  the list view resolves columns
  Then  only `id` and `name` are shown

## Acceptance criteria

- [ ] `list_display: list[str] | None = None` in AdminOptions
- [ ] `search_fields: list[str] | None = None` in AdminOptions
- [ ] Existing code passing explicit lists is unaffected
- [ ] Priority resolution in routing: `column_list` > `list_display` > `infer_list_display()`
- [ ] Unit tests for None vs [] vs explicit list behavior

## Files likely affected

- `src/hyperadmin/core/options.py`
- `src/hyperadmin/routing.py` — priority resolution
- `tests/unit/test_options.py`

## Dependencies

Depends on: #363

## Notes for implementer

The existing `column_list` mechanism in `routing.py:200-203` via `_extract_column_names()` must coexist. Priority: column_list (existing) > list_display (new) > introspection (fallback). `column_list` is NOT deprecated.

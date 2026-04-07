---
type: epic
id: -TGq_yaQZtX_
title: "epic: select & multiselect widgets (enum, FK, M2M, hybrid, autocomplete)"
status: done
priority: medium
owner: null
labels:
  - agent-task
milestone_ref:
  id: EVI7ja6oi2TX
github:
  issue_number: 159
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a81bbaea29b467cd3ada2cc1179943f7a27d10cfaa2d2e1386296a574f393043
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-20T15:35:39Z
updated_at: 2026-03-28T19:45:17Z
---

## Epic: Select & Multiselect Widgets

Part of milestone: **Phase 2: Core Feature Parity**

### Goal
Enable HyperAdmin forms to render enum dropdowns, FK selects, M2M multiselects, and HTMX-powered autocomplete — all auto-detected from SQLModel field types.

### Dependency Chain (bottom-up)

```
#160 (done: ChoicesProvider protocol)
  └─ #162 classify_field() introspection
       └─ #161 SQLModelAdapter.get_choices()
            ├─ #163 SelectWidget / MultiSelectWidget (enums/static)
            └─ #164 RelationSelectWidget / RelationMultiSelectWidget
                 ├─ #165 HTMX autocomplete endpoint
                 │    └─ #166 Dependent/cascading select endpoint
                 ├─ #167 Wire _pick_widget() auto-selection
                 ├─ #168 Multiselect form binding & value coercion
                 ├─ #169 Enum/static select templates
                 └─ #170 Relation select templates (HTMX)
                      └─ #171 Dependent cascading UI component
                           └─ #173 Pipeline unit tests
```

### Sub-issues
- [x] #160 `ChoicesProvider` protocol + `SelectFieldMeta` (done)
- [x] #162 `classify_field()` relationship introspection
- [x] #161 `SQLModelAdapter.get_choices()` with N+1 guard
- [x] #163 `SelectWidget` + `MultiSelectWidget` for enums/static
- [x] #164 `RelationSelectWidget` + `RelationMultiSelectWidget`
- [x] #165 HTMX autocomplete endpoint
- [x] #166 Dependent/cascading select endpoint
- [x] #167 Wire `_pick_widget()` for relations and hybrid
- [ ] #168 Multiselect form binding & value coercion
- [x] #169 Enum/static select + multiselect templates
- [x] #170 Relation select/multiselect templates (HTMX)
- [ ] #171 Dependent cascading select UI component
- [ ] #173 Pipeline unit tests (end-to-end without DB)

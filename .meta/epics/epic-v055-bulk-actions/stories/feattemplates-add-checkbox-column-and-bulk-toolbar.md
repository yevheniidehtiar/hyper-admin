---
type: story
id: st-v055-bulk-03
title: "feat(templates): add checkbox column, action selector, bulk form, result grid"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - frontend
  - upstream-readiness
  - H3
estimate: null
epic_ref:
  id: ep-v055-bulk-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Add the list-view UX for bulk actions: a checkbox column (rendered only when
the registered actions include at least one `bulk=True`), an action `<select>`
+ Run button in the toolbar, the Pydantic-derived parameter form template, and
the per-row result grid with a "Retry failures" link.

All interactive elements use `data-testid` per CLAUDE.md.

**Spec:** [`docs/specs/bulk-actions.md`](../../../../docs/specs/bulk-actions.md)

## Files to Change

- **Modified:** `src/hyperadmin/templates/list.html` — checkbox column, toolbar
- **New:** `src/hyperadmin/templates/components/bulk_form.html`
- **New:** `src/hyperadmin/templates/components/bulk_result.html`
- **Modified:** `src/hyperadmin/views/dynamic.py` — pass `bulk_actions` to list context

## data-testid Reference

| Element | testid |
|---|---|
| Row checkbox | `bulk-checkbox` |
| Action `<select>` | `bulk-action-select` |
| Run button | `bulk-run-btn` |
| Param form | `bulk-form` |
| Result row | `bulk-result-row` |
| Retry-failures link | `bulk-retry-link` |

## Scenarios

```
Scenario: list view without bulk actions hides the checkbox column
  Given a ModelAdmin with no @action(bulk=True)
  When  the user opens /admin/products/
  Then  the rendered table has no element with data-testid="bulk-checkbox"

Scenario: list view with at least one bulk action renders the toolbar
  Given a ModelAdmin with @action(label="Archive", bulk=True)
  When  the user opens /admin/products/
  Then  the toolbar shows a bulk-action-select containing option "Archive"
  And   each row has data-testid="bulk-checkbox"

Scenario: result page renders a row per outcome
  Given run_bulk_action returns [BulkRowResult(1,"ok",None), BulkRowResult(2,"failed","x")]
  When  the result template renders
  Then  the page has two bulk-result-row entries
  And   the "Retry failures" link targets the bulk endpoint with ids=[2]
```

## Acceptance Criteria

- [ ] Checkbox column hidden when no bulk actions registered
- [ ] Action selector populated from `bulk_actions` context
- [ ] Param form template renders Pydantic fields; preserves selected ids in hidden inputs
- [ ] Result grid renders one row per `BulkRowResult` with status badge
- [ ] "Retry failures" link is omitted when no failures exist
- [ ] E2E selectors use the `data-testid` table above (no `ha-*` class selectors)
- [ ] `poe lint` passes; visual snapshots updated if applicable

## Blocked by

- `featviews-add-run-bulk-action-endpoint`

## Parent

- Epic: `epic-v055-bulk-actions`

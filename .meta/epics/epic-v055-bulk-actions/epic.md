---
type: epic
id: ep-v055-bulk-01
title: "epic(actions): bulk actions with Pydantic parameter forms"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - backend
  - frontend
  - upstream-readiness
  - H3
milestone_ref:
  id: v055-bulk-ac-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Overview

Implements upstream readiness capability **H3**: bulk-mode `@action` decorator,
list-view checkbox column with action selector, optional Pydantic param form
collected before execution, per-row outcome page, and `requires_selection=True`
enforcement. Permission re-check runs per row inside the bulk handler.

**SDD:** [`docs/specs/bulk-actions.md`](../../../docs/specs/bulk-actions.md)
(required — touches `core/`, `views/`, templates).

## Tracks

### Track A: Decorator + metadata
- Extend `ActionDef` with `bulk: bool`, `form: type[BaseModel] | None`.
- Extend `@action` decorator with `bulk=`, `form=` kwargs and decoration-time validation.
- Handler signature validation (`(self, request, item_id, *, params=None)`).

### Track B: Endpoints + per-row execution
- `DynamicModelView.run_bulk_action` — POST `/{model}/actions/{name}/bulk`.
- `DynamicModelView.confirm_bulk_action` — POST `/{model}/actions/{name}/bulk/confirm`.
- `BulkRowResult` NamedTuple, per-row error capture, object-permission re-check.
- `requires_selection` enforcement (server-side 400 if `ids` empty).

### Track C: Templates + list-view UX
- Checkbox column in `list.html` (rendered only when bulk actions exist).
- Action `<select>` + Run button in list toolbar.
- `components/bulk_form.html` — Pydantic form rendered with hidden `ids[]`.
- `components/bulk_result.html` — per-row status grid + "Retry failures" link.
- `data-testid` selectors for E2E (`bulk-checkbox`, `bulk-action-select`,
  `bulk-run-btn`, `bulk-result-row`, `bulk-retry-link`).

## Scenarios

(See SDD for the full set; six scenarios listed under `## BDD Scenarios`.)

## Acceptance Criteria

- [ ] `@action(bulk=True)` accepted; legacy `@action(...)` still works
- [ ] `@action(form=X)` without `bulk=True` raises `TypeError` at decoration time
- [ ] Handler signature validated at decoration time
- [ ] Bulk endpoint enforces `requires_selection` (400 on empty ids)
- [ ] Param form rendered and prefilled with selected ids
- [ ] Per-row result page lists ok / failed / forbidden per id
- [ ] Object-level permissions are re-checked per row
- [ ] "Retry failures" link re-submits only failed ids
- [ ] HTMX request returns swap-friendly fragment; non-HTMX returns full page
- [ ] Checkbox column rendered only when bulk actions exist
- [ ] Unit tests for `ActionDef`/`@action` validation
- [ ] E2E tests for all six scenarios
- [ ] `poe lint` and `poe test` pass

## Blocked by

- `reviewspec-approve-sdd-bulk-actions` (SDD approved)

## Parent

- Milestone: `v055-bulk-actions-autocomplete`
- Tracking: `epic-upstream-readiness` (H3)

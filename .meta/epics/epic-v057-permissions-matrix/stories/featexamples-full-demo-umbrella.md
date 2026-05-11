---
type: story
id: st-v057-pmx-04
title: "feat(examples): full-demo umbrella app + qualification E2E suite"
status: todo
priority: high
assignee: null
labels:
  - size:L
  - planned
  - examples
  - tests
  - upstream-readiness
estimate: null
epic_ref:
  id: ep-v057-pmx-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Ship `examples/full-demo/` — the umbrella example app exercising every H#
capability with framework-neutral domain models (`Order`, `Invoice`,
`Product`, `Supplier`). Per-feature `examples/<name>/` apps remain. Add a
`poe test:e2e -k qualification` suite that runs the ten readiness checks
end-to-end against the umbrella app; this becomes the readiness gate.

**Spec:** [`docs/specs/permission-matrix-ui.md`](../../../../docs/specs/permission-matrix-ui.md)
(only as the umbrella-bundle decision lives here)

## Files to Change

- **New:** `examples/full-demo/main.py`
- **New:** `examples/full-demo/models.py` — `Order`, `Invoice`, `Product`, `Supplier` (generic)
- **New:** `examples/full-demo/admins.py` — `OrderAdmin`, `InvoiceAdmin`, etc.
- **New:** `examples/full-demo/seed.py`
- **New:** `examples/full-demo/static/sample.pdf` — for the H4 PDF panel demo
- **New:** `tests/e2e/test_qualification.py` — ten checks per `epic-upstream-readiness` epic body
- **Modified:** `pyproject.toml` — `poe test:e2e:qualification` task

## Scenarios → Qualification Checks

Each check maps directly to one row in `epic-upstream-readiness`'s
acceptance list:

| # | Capability | Test function |
|---|---|---|
| 1 | H2 polish (row error highlight) | `test_h2_inline_row_error_highlight` |
| 2 | H3 bulk action 5 rows, 1 fails | `test_h3_bulk_action_per_row_outcome` |
| 3 | H4 detail panels w/ PDF demo | `test_h4_detail_panels_with_pdf` |
| 4 | H5 IsOwnerFilter | `test_h5_list_filter_by_owner` |
| 5 | H6 dependent FK + popup | `test_h6_dependent_fk_autocomplete_and_popup` |
| 6 | H12 sidebar + saved view | `test_h12_filter_sidebar_and_saved_view` |
| 7 | H13 JPEG upload thumbnail | `test_h13_jpeg_upload_thumbnail` |
| 8 | H14 OLAP report + CSV/XLSX | `test_h14_olap_report_csv_xlsx` |
| 9 | H15 chart bound to dataset | `test_h15_chart_bound_to_report` |
| 10 | H20 matrix flip view-but-not-edit | `test_h20_matrix_flips_view_not_edit` |

## Acceptance Criteria

- [ ] `uv run examples/full-demo/main.py` boots without errors
- [ ] Generic schema only — no consumer-specific names (per project rule)
- [ ] Per-feature `examples/<name>/` apps remain untouched
- [ ] All ten qualification tests pass on develop
- [ ] `poe test:e2e:qualification` defined and wired into CI
- [ ] README under `examples/full-demo/` documents the boot + qualification flow

## Blocked by

- `feattemplates-matrix-and-popover`
- All prior upstream-readiness epics

## Parent

- Epic: `epic-v057-permissions-matrix`

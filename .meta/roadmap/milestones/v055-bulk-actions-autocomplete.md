---
type: milestone
id: v055-bulk-ac-01
title: v0.5.5 — Bulk Actions & Autocomplete
status: in_progress
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

**Roadmap position 2/16 (2026-09-28 re-cut).** Finish what is half-merged: #559/#560/#563/#566 and the H2 polish (#561) are on develop; the list-view bulk toolbar, `AutocompleteWidget` template and Playwright suites remain.

H3 + H6 from upstream readiness. Bulk actions with Pydantic parameter forms,
per-row outcome reporting, and `requires_selection=True` wiring; HTMX FK/M2M
autocomplete with dependent filtering, create-on-the-fly popup, and configurable
display template per relation. Foundational for any consumer admin build.

Spec: `docs/specs/bulk-actions.md`, `docs/specs/htmx-autocomplete.md`.
Tracking: `.meta/epics/epic-upstream-readiness/` (H3, H6).

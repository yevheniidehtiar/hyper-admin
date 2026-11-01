---
type: story
id: st-v059-nav-03
title: "feat(nav): per-user pinned models in the sidebar"
status: backlog
priority: high
assignee: null
labels:
  - size:L
  - planned
  - area:core
  - backend
  - frontend
estimate: null
epic_ref:
  id: ep-v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Add the `navigation/` package with `NavPin` (`hyperadmin_nav_pin`) and `NavPinService` (mirrors `SavedViewService`), the `POST`/`DELETE {prefix}/nav/pins` endpoints in `views/nav_pins.py`, a "Pinned" group at the top of the sidebar, and a pin toggle per item. Off when there is no `user_key`.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **New:** `src/hyperadmin/navigation/__init__.py`, `navigation/pins.py`
- **New:** `src/hyperadmin/views/nav_pins.py`, `templates/components/nav_pinned.html`
- **Modified:** `src/hyperadmin/templates/_sidebar.html`, `src/hyperadmin/core/app.py`, `src/hyperadmin/core/settings.py`
- **Modified:** `docs/guides/existing-app.md`
- **New:** `tests/unit/test_nav_pins.py`, `tests/e2e/test_nav_pins.py`

## Scenarios

```
Scenario: pinning a model adds it to the Pinned group
  Given alice is signed in with no pins
  When  alice pins Orders
  Then  the Pinned group shows Orders and the toggle has aria-pressed="true"

Scenario: pins follow the user to another browser
  Given alice pinned Orders
  When  alice signs in from a new browser context
  Then  Orders is in her Pinned group

Scenario: pins are per user
  Given alice pinned Orders
  When  bob opens the dashboard
  Then  bob has no Pinned group

Scenario: a pin the user can no longer view is hidden
  Given alice pinned Invoices and then loses view_invoice
  When  alice opens the dashboard
  Then  Invoices is not shown in Pinned

Scenario: unknown or forbidden pin targets return 404
  When  alice POSTs target="secretmodel"
  Then  the response is 404

Scenario: a pin beyond the limit is refused
  Given nav_pins_max is 20 (default) and alice has 20 pins
  When  alice pins another page
  Then  the response is 409 and an error toast explains the limit

Scenario: no auth means no pins
  Given HyperAdmin without auth
  When  the dashboard renders
  Then  no pin toggles are rendered and /nav/pins is not routed
```

## Acceptance Criteria

- [ ] `HyperAdminSettings.nav_pins_max: int = 20` (`ge=1`, env `HYPERADMIN_NAV_PINS_MAX`) documented in the settings reference
- [ ] Table joins `hyperadmin_*` metadata on import (`init-db`, `auth.metadata()`)
- [ ] Missing table: logged once, feature hidden, no 500 (same guard as saved views)
- [ ] Double POST is idempotent (unique constraint handled)
- [ ] CSRF enforced by the existing `CsrfGuard`
- [ ] `docs/guides/existing-app.md` §5 gains the `hyperadmin_nav_pin` operation
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass
- [ ] E2E tests map 1:1 to the scenarios, use role/label/test-id locators only, with `# Given / # When / # Then` comments
- [ ] Visual baselines refreshed on Linux (`RESPONSIVE_SNAPSHOTS_UPDATE=1`) where the UI changed
- [ ] Manual test scenarios attached to the PR
- [ ] New `data-testid`s added to the CLAUDE.md reference table

## Notes for Implementer

Copy the `filters/saved_views.py` structure (service, `open_session`, `UTCNaiveDateTime`). Pin target keys: model slug or `plugin:<url_name>`.

## Blocked by

- `feattemplates-grouped-collapsible-sidebar-with-icon-rail` (st-v059-nav-02)

## Parent

- Epic: `epic-v059-navigation`

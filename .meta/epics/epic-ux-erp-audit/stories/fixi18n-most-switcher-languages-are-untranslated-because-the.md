---
type: story
id: st-ux-erp-10
title: "fix(i18n): most switcher languages are untranslated because their catalogs are fuzzy"
status: backlog
priority: high
assignee: null
labels:
  - planned
  - bug
  - i18n
  - area:i18n
  - size:M
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:08.924Z
updated_at: 2026-11-07T07:21:08.924Z
---

## Summary

The locale switcher offers ~20 languages, but de/ar/fr/es/ja and others barely change the UI: 45 of 54 entries are AI drafts marked `#, fuzzy` (#550), and `pybabel compile` skips fuzzy entries (`de` .mo = 445 bytes). Only `uk` is really translated.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- German and Arabic captures: "Create", "Cancel", "Filters", "Menu" stay English; RTL mirroring works.

## Files to Change

- **Modified:** `src/hyperadmin/locale/*/LC_MESSAGES/messages.po` (review, drop `fuzzy`), compiled `.mo`
- **Modified:** locale settings (offer only locales above a completeness threshold) or docs

## Scenarios

```
Scenario: switching to German translates the chrome
  Given locale de
  When  the invoice create form renders
  Then  the buttons read "Erstellen" and "Abbrechen"
```

## Acceptance Criteria

- [ ] Each offered locale has no fuzzy entries in the shipped catalog
- [ ] CI check fails when a shipped catalog has fuzzy entries


---
type: epic
id: ep-ux-erp-01
title: "epic(ux): ERP showcase UX audit fixes"
status: backlog
priority: high
owner: null
labels:
  - planned
  - area:templates
  - frontend
  - ui
  - accessibility
  - responsive
milestone_ref: null
created_at: 2026-11-07T07:18:45.793Z
updated_at: 2026-11-07T07:18:45.793Z
---

## Overview

Fix what the UI/UX audit of the ERP showcase (`examples/erp`) found on `develop` @ `0014cc1` (2026-11-06). The audit
covered 51 pages on 360/393 phones, 768/1180 tablets, a 1280 laptop and a 1920 desktop, in light and dark mode, plus
hidden states (validation errors, save, dialogs, German and Arabic). Ranked by user impact; the two P0 bugs block the
core task of the showcase: invoices and bills can't be saved.

Already good (no work): text contrast passes everywhere, dark mode is consistent, every control is labelled, the delete
dialog and RTL mirroring work.

## Stories

| P | ID | Story |
|---|---|---|
| P0 | st-ux-erp-01 | fix(forms): saving a model with a relationship named `items` returns 500 |
| P0 | st-ux-erp-02 | fix(widgets): FK select drops the current value outside the preloaded options |
| P0 | st-ux-erp-03 | fix(templates): show an error when a form submit fails with a server error |
| P1 | st-ux-erp-04 | feat(templates): format money and decimal values |
| P1 | st-ux-erp-05 | fix(templates): navbar overflows 360px phones and truncates the brand |
| P1 | st-ux-erp-06 | fix(forms): readable validation messages and an error summary |
| P1 | st-ux-erp-07 | feat(widgets): render `date` fields with a date input |
| P1 | st-ux-erp-08 | fix(templates): wide lists hide columns on tablets |
| P1 | st-ux-erp-09 | fix(css): 44px touch targets for sidebar toggles, pins and sort links |
| P1 | st-ux-erp-10 | fix(i18n): switcher languages untranslated (fuzzy catalogs) |
| P2 | st-ux-erp-11 | fix(templates): verbose names instead of class/field names |
| P2 | st-ux-erp-12 | fix(widgets): one control per FK field |
| P2 | st-ux-erp-13 | feat(templates): status pills with an overdue variant |
| P2 | st-ux-erp-14 | feat(templates): phone list card hierarchy |
| P2 | st-ux-erp-15 | style(templates): de-emphasise destructive actions |
| P2 | st-ux-erp-16 | style(templates): sidebar pins on hover/focus only |
| P2 | st-ux-erp-17 | fix(examples): one name for the P&L report |
| P2 | st-ux-erp-18 | fix(templates): Permission matrix empty state action |
| P3 | st-ux-erp-19 | feat(examples): ERP dashboard KPIs (needs decision) |
| P3 | st-ux-erp-20 | feat(examples): ERP invoice list workflow (needs decision) |

## Out of scope

- Visual redesign beyond the findings.

Screenshots and the full report are available from the audit run on request.

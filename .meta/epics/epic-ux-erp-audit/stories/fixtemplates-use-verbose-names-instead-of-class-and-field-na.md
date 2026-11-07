---
type: story
id: st-ux-erp-11
title: "fix(templates): use verbose names instead of class and field names in titles, buttons and FK labels"
status: backlog
priority: medium
assignee: null
labels:
  - planned
  - enhancement
  - ui
  - area:templates
  - area:examples
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:09.452Z
updated_at: 2026-11-07T07:21:09.452Z
---

## Summary

Code names leak into the UI: "JournalLine List", "Create New JournalLine", "Add InvoiceItem" (`inline_formset.html` uses `model.__name__`), "Customer id" / "Search customer id" (FK labels keep `_id`), and rows titled "JournalEntry (1)" (no `__str__` on the demo model).

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- `/admin/journalline`, `/admin/invoice/create` on every device.

## Files to Change

- **Modified:** `src/hyperadmin/templates/list_layout.html`, `components/inline_formset.html` (verbose names)
- **Modified:** `src/hyperadmin/views/forms.py` (FK label drops `_id`)
- **Modified:** `examples/erp/accounting/models.py` (readable `__str__`)

## Scenarios

```
Scenario: titles use the plural verbose name
  Given the JournalLine admin
  Then  the list title reads "Journal lines" and the button "Create journal line"
```

## Acceptance Criteria

- [ ] No CamelCase class names or `_id` suffixes in rendered text


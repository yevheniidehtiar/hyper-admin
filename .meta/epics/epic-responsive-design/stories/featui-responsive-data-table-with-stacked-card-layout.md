---
type: story
id: KKpriYWS0U9B
title: "feat(ui): responsive data table with stacked card layout"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - ui
  - size:M
  - planned
  - responsive
  - cycle:1
estimate: null
epic_ref:
  id: RspSynth_01
github:
  issue_number: 461
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5b0a00170b65ac0b51f52e731297f1b40b19567e2e16b6377bc67270912492ab
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:49Z
updated_at: 2026-04-01T21:44:49Z
---

## Summary

Below 768px viewport, transform the data table from horizontal rows into stacked cards. Each card shows field labels inline with values. Action buttons displayed as a footer row in each card. Table header row visually hidden on mobile but remains in DOM for accessibility.

Uses self-contained `@media` queries within `_table.css` -- no dependency on `_responsive.css` changes. This allows it to run in parallel with C1-B (base layout rewrite) in Cycle 1.

## Scenarios

**Scenario: table displays as stacked cards on mobile**
  Given viewport width is 375px
  When  the list view loads with data
  Then  each table row renders as a card with vertical layout
  And   each cell shows a label (column name) and value side by side

**Scenario: table displays as normal table on desktop**
  Given viewport width is 1024px
  When  the list view loads with data
  Then  the table renders as a standard horizontal table with headers

**Scenario: action buttons appear in card footer on mobile**
  Given viewport width is 375px
  When  the list view loads with data
  Then  View, Edit, and Delete actions appear at the bottom of each card
  And   action buttons have minimum 44px touch targets

**Scenario: card layout uses data-label attributes for inline labels**
  Given the table template includes data-label attributes on cells
  When  CSS displays cards on mobile
  Then  the data-label content appears as bold text before each value

**Scenario: table header remains accessible to screen readers on mobile**
  Given viewport width is 375px and a screen reader is active
  When  the list view loads with data
  Then  the table header row is visually hidden but present in the accessibility tree

## Acceptance criteria

- [ ] Table displays as stacked cards on mobile
- [ ] Table displays as normal horizontal table on desktop
- [ ] Action buttons in card footer on mobile with 44px touch targets
- [ ] data-label attributes provide inline column labels
- [ ] Table header accessible to screen readers when visually hidden

## Files to modify

- `src/hyperadmin/templates/components/table.html` -- add `data-label` attribute to `<td>` elements
- `src/hyperadmin/static/css/_table.css` -- card layout styles with self-contained `@media (max-width: 767px)` query (no `_responsive.css` changes -- keeps story independent for Cycle 1 parallelism)

## Implementation notes

- `thead { position: absolute; clip: rect(0,0,0,0); }` on mobile (accessible hide)
- `tr { display: block; margin-bottom: 1rem; border; border-radius; padding; }`
- `td { display: flex; justify-content: space-between; }`
- `td::before { content: attr(data-label); font-weight: 600; }`
- Actions column `<td>` gets `data-label="Actions"` with horizontal layout in card mode
- Inline formset tables should also use this pattern

## Demo checkpoint

Open any list view (e.g. /admin/contact/) at 375px viewport:
1. Verify each row renders as a card with label:value pairs stacked vertically
2. Verify column headers are visually hidden but accessible
3. Verify View/Edit/Delete buttons appear at card bottom with 44px touch targets
4. Widen to 1024px -- verify standard horizontal table layout restored

**This is the FIRST demoable mobile feature** -- available at end of Cycle 1.

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** none -- self-contained card CSS in _table.css with own media queries

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
estimate: null
epic_ref: Rsp4_Gamma_01
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

**Scenario: card layout is accessible to screen readers**
  Given viewport width is 375px and a screen reader is active
  When  the list view loads with data
  Then  each card has role="article" or is wrapped in a semantic element
  And   the visually hidden table headers remain accessible to screen readers
  And   each card's data-label is associated with its value via aria-label or visible text

## Acceptance criteria

- [ ] Table displays as stacked cards on mobile
- [ ] Table displays as normal horizontal table on desktop
- [ ] Action buttons in card footer on mobile with 44px touch targets
- [ ] data-label attributes provide inline column labels
- [ ] Card layout is accessible to screen readers (semantic roles, hidden headers)

## Files to modify

- `src/hyperadmin/templates/components/table.html` — add `data-label` attribute to `<td>` elements
- `src/hyperadmin/static/css/_table.css` — card layout base styles
- `src/hyperadmin/static/css/_responsive.css` — table card transformation at mobile breakpoint

## Implementation notes

- `thead { position: absolute; clip: rect(0,0,0,0); }` on mobile (accessible hide)
- `tr { display: block; margin-bottom: 1rem; border; border-radius; padding; }`
- `td { display: flex; justify-content: space-between; }`
- `td::before { content: attr(data-label); font-weight: 600; }`
- Actions column `<td>` gets `data-label="Actions"` with horizontal layout in card mode
- Inline formset tables should also use this pattern

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** #452

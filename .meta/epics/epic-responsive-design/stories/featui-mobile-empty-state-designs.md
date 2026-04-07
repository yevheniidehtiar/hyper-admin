---
type: story
id: Rsp4_empt_09
title: "feat(ui): mobile-friendly empty state designs"
status: todo
priority: low
assignee: null
labels:
  - frontend
  - ui
  - size:S
  - planned
  - responsive
estimate: null
epic_ref: Rsp4_Gamma_01
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Summary

When the list view has no records, or search returns no results, the empty state message should be visually appealing on mobile. Currently it is just text in an empty table. Add a centered, friendly empty state with an icon and a "Create New" call-to-action button that is easy to tap on mobile.

## Scenarios

**Scenario: empty list shows friendly message on mobile**
  Given viewport width is 375px and a model has no records
  When  the list view loads
  Then  a centered empty state message is displayed with an icon
  And   a "Create New" button is prominently displayed with 44px touch target

**Scenario: empty search results show contextual message**
  Given viewport width is 375px and the user searches for a non-existent term
  When  the search results load
  Then  an empty state message says "No results found for [search term]"
  And   a "Clear search" link is displayed

**Scenario: empty state icon has accessible alternative text**
  Given viewport width is 375px and a screen reader is active
  When  the empty list state loads
  Then  the decorative icon has aria-hidden="true"
  And   the message text is the primary accessible content

## Acceptance criteria

- [ ] Empty list state has icon + message + Create New CTA on mobile
- [ ] Empty search state has contextual message + Clear search link
- [ ] Both states are centered and visually appealing on 375px
- [ ] Empty state icon is decorative (aria-hidden) with accessible message text

## Files to modify

- `src/hyperadmin/templates/components/table.html` -- add empty state block
- `src/hyperadmin/static/css/_table.css` -- empty state styling
- `src/hyperadmin/static/css/_responsive.css` -- mobile empty state adjustments

## Implementation notes

- Empty state div: `text-align: center; padding: var(--ha-space-12) var(--ha-space-4);`
- Use a simple SVG icon (empty box or magnifying glass) inline in the template
- "Create New" button uses existing `.ha-btn .ha-btn-primary` classes
- Conditional: show "Clear search" only when search query is active

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #461

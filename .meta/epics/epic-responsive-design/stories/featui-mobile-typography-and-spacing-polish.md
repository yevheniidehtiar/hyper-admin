---
type: story
id: Rsp4_typo_08
title: "feat(ui): mobile typography and spacing polish"
status: cancelled
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

Fine-tune typography scale and spacing for mobile viewports. On small screens, the current heading sizes and content padding are slightly too generous, wasting precious vertical space. Reduce page header size, tighten card spacing, and ensure comfortable reading without excessive whitespace.

## Scenarios

**Scenario: page headings are appropriately sized on mobile**
  Given viewport width is 375px
  When  a list view page loads
  Then  the page heading (h1) uses font-size-xl instead of font-size-2xl
  And   the subheading text is appropriately scaled

**Scenario: content area uses mobile-optimized padding**
  Given viewport width is 375px
  When  any admin page loads
  Then  the content area uses --ha-space-4 padding instead of --ha-space-8
  And   cards and tables have reduced margin-bottom

## Acceptance criteria

- [ ] Page headings reduced on mobile (xl instead of 2xl)
- [ ] Content area padding reduced on mobile
- [ ] Card/table spacing tightened on mobile
- [ ] No horizontal overflow from any text content

## Files to modify

- `src/hyperadmin/static/css/_page-header.css` -- responsive heading sizes
- `src/hyperadmin/static/css/_responsive.css` -- mobile spacing overrides

## Implementation notes

- `.ha-content` already gets `padding: var(--ha-space-4)` at mobile via `_responsive.css`
- Add heading scale reduction: `h1 { font-size: var(--ha-font-size-xl); }` at mobile
- `.ha-table-wrapper { margin: var(--ha-space-4) 0; }` instead of `--ha-space-6` on mobile
- Ensure `word-break: break-word;` on content area to prevent overflow from long strings

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #452

---
type: story
id: RspSyn_C1A_01
title: "refactor(ui): add breakpoint design tokens to _tokens.css"
status: todo
priority: high
assignee: null
labels:
  - frontend
  - css
  - size:S
  - responsive
  - cycle:1
estimate: null
epic_ref:
  id: RspSynth_01
github: null
created_at: 2026-04-08T00:00:00Z
updated_at: 2026-04-08T00:00:00Z
---

## Summary

Add responsive breakpoint custom properties to `_tokens.css`. This is a pure additive
change -- no existing styles are modified. Provides the shared vocabulary (design tokens)
all other responsive stories consume.

Split from #452 (Cycle 1, Slot A).

## Scenarios

**Scenario: breakpoint tokens are defined as design tokens**
  Given the HyperAdmin CSS loads
  When  inspecting :root custom properties
  Then  --ha-bp-sm (640px), --ha-bp-md (768px), --ha-bp-lg (1024px), --ha-bp-xl (1280px) are defined

**Scenario: sidebar width tablet token exists**
  Given the HyperAdmin CSS loads
  When  inspecting :root custom properties
  Then  --ha-sidebar-width-tablet (12rem) is defined

## Acceptance criteria

- [ ] Breakpoint tokens --ha-bp-sm, --ha-bp-md, --ha-bp-lg, --ha-bp-xl defined in :root
- [ ] --ha-sidebar-width-tablet token defined

## Files to modify

- `src/hyperadmin/static/css/_tokens.css` -- add breakpoint tokens and sidebar-width-tablet

## Implementation notes

- Add tokens at the end of the `:root` block under a `/* ---- Breakpoints ---- */` comment
- Values: sm=640px, md=768px, lg=1024px, xl=1280px
- Add `--ha-sidebar-width-tablet: 12rem;` under `/* ---- Layout ---- */`
- This is purely additive -- zero risk of regression

## Demo checkpoint

Open any admin page, inspect `:root` in DevTools, confirm new custom properties are present.

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** none

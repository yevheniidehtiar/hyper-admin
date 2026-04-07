---
type: story
id: mHOj6CWj_8vX
title: "feat(ui): mobile scroll-to-top after HTMX navigation"
status: todo
priority: medium
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

On mobile, after an HTMX swap (pagination, search, sort, filter), the user is often left scrolled far down the page staring at the pagination footer. The content has changed above them but they cannot see it. Add automatic scroll-to-top behavior after HTMX content swaps, using the existing `htmx:afterSwap` event. Also add `scroll-padding-top` to account for the fixed navbar so anchored content is not hidden behind it.

## Scenarios

**Scenario: page scrolls to top after HTMX pagination swap on mobile**
  Given viewport width is 375px and the list view is scrolled to the bottom
  When  the user taps the Next page button (triggering HTMX swap)
  Then  the page smoothly scrolls to the top of the list content area
  And   the first card is fully visible below the navbar

**Scenario: scroll respects reduced-motion preference**
  Given the user has prefers-reduced-motion enabled
  When  an HTMX swap triggers scroll-to-top
  Then  the scroll happens instantly without smooth animation

## Acceptance criteria

- [ ] After HTMX pagination/search/sort/filter swaps, page scrolls to top of list content
- [ ] Scroll accounts for fixed navbar height (scroll-padding-top)
- [ ] Scroll respects prefers-reduced-motion (instant jump, no smooth scroll)
- [ ] No new JavaScript dependencies — uses htmx:afterSwap event listener

## Files to modify

- `src/hyperadmin/templates/list_layout.html` -- add htmx:afterSwap scroll handler
- `src/hyperadmin/static/css/_layout.css` -- add scroll-padding-top for fixed navbar

## Implementation notes

- Listen for `htmx:afterSwap` on the list content container
- `document.querySelector('.ha-content').scrollIntoView({ behavior: 'smooth' })`
- In `_layout.css`: `html { scroll-padding-top: calc(var(--ha-navbar-height, 3.5rem) + var(--ha-space-2)); }`
- For reduced-motion: check `window.matchMedia('(prefers-reduced-motion: reduce)')` and use `behavior: 'instant'`
- This can be implemented inline in the template as a small `<script>` tag (3-4 lines)

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** #452

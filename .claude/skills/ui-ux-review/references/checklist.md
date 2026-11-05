# UI/UX review checklist

Use it per page and per device. Look at the screenshot first, then the checklist. A "no" is a
finding only if you can say what it costs the user.

## Hierarchy and first glance
- [ ] Within 3 seconds it's clear where I am (page title, active nav item, breadcrumb) and what the page is for.
- [ ] One primary action per screen, visually dominant; secondary actions are quieter; destructive ones are clearly separate.
- [ ] The most-used content is above the fold on a phone (360×740), not pushed down by chrome, filters or banners.
- [ ] Squint test: the visual weight order matches the importance order.

## Layout and spacing
- [ ] No horizontal page scroll at any width; wide tables scroll inside their own container, with a visible hint.
- [ ] Spacing comes from the `--ha-space-*` scale and is consistent: related items close, groups clearly separated.
- [ ] Edges line up (labels, inputs, table columns, card padding); no element is 1–3px off.
- [ ] Desktop 1920: content width and line length stay readable (forms ≤ ~720px, prose ≤ ~75ch); no huge empty gutters or stretched inputs.
- [ ] Tablet 768–1180: the sidebar and content split doesn't squeeze tables into unreadable columns.
- [ ] Landscape phone: sticky header + footer leave usable room; dialogs fit or scroll.

## Typography
- [ ] Body ≥ 16px on phones (inputs ≥ 16px, or iOS zooms on focus); nothing under 12px.
- [ ] A clear type scale (title > section > label > body > meta) with no more than ~4 sizes per screen.
- [ ] Long values (names, emails, IDs, German words) wrap or truncate with an ellipsis + full text in a tooltip or title; nothing overlaps.
- [ ] Numbers in tables are right-aligned with tabular figures.

## Colour and dark mode
- [ ] Text contrast ≥ 4.5:1 (≥ 3:1 for large text); UI component borders and focus rings ≥ 3:1 (WCAG 1.4.11).
- [ ] Colour is never the only signal (status, errors, required): add an icon, text or shape.
- [ ] Dark mode: no pure-white blocks, images or charts glaring out; borders still visible; shadows replaced by surface steps; brand/danger colours desaturated enough to read.
- [ ] Hover, focus, selected and disabled states are distinguishable in both themes.

## Touch and interaction
- [ ] Targets ≥ 44×44px on touch (≥ 24px everywhere), with ≥ 8px between neighbouring targets; destructive actions not next to frequent ones.
- [ ] Nothing depends on hover on touch devices (tooltips, row actions revealed on hover, menus).
- [ ] Primary actions within thumb reach on phones (bottom half or a sticky action bar for long forms).
- [ ] A visible focus ring on every focusable element; logical tab order; Esc closes overlays; focus returns to the trigger.

## Forms
- [ ] Every field has a visible label (placeholders don't count) and the required ones are marked consistently.
- [ ] Right input types/modes (`email`, `tel`, `number`, `date`, `inputmode`) so phones show the right keyboard.
- [ ] Errors sit next to the field, say how to fix it, and the first error is scrolled to and focused; a summary appears for long forms.
- [ ] One column on phones; logical grouping (fieldsets) on wide screens; no duplicated controls for one value.
- [ ] Submit and cancel are predictable and placed the same on every form; destructive Delete is separate and confirmed.

## Tables and lists
- [ ] On phones rows become readable cards: the key field first, labels on values, actions reachable.
- [ ] Column headers show sort state; the sticky header works; numeric/date columns align.
- [ ] Row click target and explicit actions don't fight each other (no accidental opens when selecting).
- [ ] Pagination shows where I am and the total, and is touch-sized; filters show the active count and can be cleared in one tap.
- [ ] Bulk selection shows how many are selected and what the action will affect.

## Feedback and states
- [ ] Empty state explains why it's empty and offers the next action (create, clear filters).
- [ ] Loading state for anything > 300ms (HTMX requests, reports); no layout jump when content arrives.
- [ ] Success/error messages are visible on a phone without scrolling, announced to screen readers (`role=status`/`alert`), and don't cover primary actions.
- [ ] Destructive actions confirm with the object's name and say what is lost; there's undo where possible.
- [ ] Error pages (403/404/500) explain what happened and offer a way back.

## Navigation
- [ ] Phone: the menu opens from a clear button, traps focus, closes on Esc, close button or a backdrop tap, and shows the current page.
- [ ] Long model lists in the sidebar are grouped or searchable; pinned/recent items are reachable.
- [ ] Back and cancel return to where the user came from (the list with its filters, page and sort kept).

## Content, i18n and RTL
- [ ] Labels are human (`Created at`, not `created_at`); button verbs name the outcome (`Archive 3 orders`).
- [ ] German/French strings (30–40% longer) don't break buttons or nav; CJK text isn't clipped.
- [ ] `ar`/`he`: the layout mirrors (sidebar, icons with direction, alignment), numbers and Latin IDs stay LTR, no `left`/`right` leftovers.

## Accessibility (beyond the automated checks)
- [ ] One `<h1>`, logical heading levels, landmarks (`header`, `nav`, `main`).
- [ ] Icon-only buttons have an accessible name that says the action and target (`Delete Acme`).
- [ ] 200% zoom and 320px reflow work without loss of content (WCAG 1.4.10).
- [ ] Motion respects `prefers-reduced-motion`; `forced-colors` keeps borders and focus visible.

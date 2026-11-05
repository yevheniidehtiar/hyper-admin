---
name: ui-ux-review
description: "UI/UX expert review of the HyperAdmin admin UI: screenshot every page on phone, tablet, laptop and desktop in light and dark mode, walk through it as real users, rank the problems, then fix the design in templates/CSS and prove it with before/after screenshots. Use when asked to review, audit, polish or improve the UI, UX, design, responsiveness, mobile view, dark mode or accessibility of the admin, or after a UI-affecting change."
argument-hint: "[audit|fix] [paths or feature, e.g. /admin/order or 'list view'] [--app full-demo|simple|erp]"
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(uv run *), Bash(git *), Bash(curl *), Bash(gh *)
---

# UI/UX expert review

You are a senior product designer and accessibility specialist reviewing the HyperAdmin admin
UI. You judge the UI by **what users see and do on their device**, not by reading the code. Every
claim you make points at a screenshot. Every change you make is checked in a new screenshot.

Arguments: `$ARGUMENTS`
- `audit` (default): capture, review and report. Don't change code.
- `fix`: audit, then carry out the P0/P1 improvements (and cheap P2s) and re-capture.
- Paths/feature: limit the review to those pages. Without them, the sidebar is discovered (all models, plus one list, detail, edit and create page each).
- `--app`: demo app to boot (default `full-demo`, the one with the most features).

## 1. Set up

Work in a worktree branched from `develop` (see `/wt`) when the mode is `fix`.

Boot the demo on a free port in the background and wait for it:

```bash
E2E_TESTING=1 uv run --directory examples/full-demo uvicorn main:app --port 8765   # run_in_background
curl -s http://127.0.0.1:8765/          # until it answers
```

Credentials: full-demo `alice` / `secret123`. For `simple`, use `--directory examples/simple` (no login).
`E2E_TESTING=1` gives a throwaway database, so the review never changes `full_demo.db`.

## 2. Capture

```bash
uv run python .claude/skills/ui-ux-review/scripts/capture.py \
  --base-url http://127.0.0.1:8765 --login alice:secret123 \
  --out .ux-review/before            # add --paths /admin/order,/admin/order/1/edit to scope
```

Default device matrix (`--devices`, `--themes light,dark`):

| device | viewport | why |
|---|---|---|
| `phone-small` | 360×740 touch | smallest common Android, worst-case wrapping |
| `phone` | 393×852 touch | iPhone 15/16 |
| `phone-landscape` | 852×393 touch | opt-in: short height, sticky headers, dialogs |
| `tablet` | 768×1024 touch | `--ha-bp-md`: sidebar appears, tables stop being cards |
| `tablet-landscape` | 1180×820 touch | touch at desktop width: hover-only UI breaks here |
| `laptop` | 1280×800 | `--ha-bp-xl`, the design target's lower edge |
| `desktop` | 1920×1080 | the design target's upper edge: line length, empty space |

Output: `.ux-review/<run>/<page>/<device>-<theme>.png`, `findings.json` (automated checks),
`index.md`. The automated checks are **leads, not verdicts**. They find horizontal scroll,
elements cut off at the screen edge, tap targets (24px minimum, 44px on touch), text contrast
(WCAG 4.5:1 / 3:1), tiny text on phones, text cut off without an ellipsis, controls with no
label or name, the `<h1>` count, console errors and HTTP errors. They skip elements hidden on
purpose (sr-only text, skip links, closed drawers) and merge repeated rows into one finding
with a `count`.

## 3. Review like a user

Open the screenshots with the Read tool (it shows images). For each page, view the phone, the
tablet and the desktop shots, in light and then dark mode. Don't review from the HTML. Pick the
persona and task that fit the page, and walk the task one screen at a time:

- **Ops on a phone**, on the move, one thumb: find order ORD-2, check its status, change it.
- **Back-office clerk on a laptop**, 6 hours a day: scan a 50-row list, filter, bulk-archive, edit.
- **Manager on a tablet**, mostly reading: open a report, compare periods, export.
- **First-time admin user**: no training. Is it obvious what to click first?

For each screen ask: what does the user see first? Is it the most important thing? What do they
do next, and can they reach it without scrolling or hunting? What would make them hesitate,
mis-tap or give up?

Score every page against [references/checklist.md](references/checklist.md). It covers
hierarchy, layout and spacing, typography, colour and dark mode, touch and interaction, forms,
tables and lists, feedback and states, navigation, content and i18n/RTL, and accessibility.
Check the states a static screenshot hides by driving them in the capture context, or with a
short Playwright snippet: empty list, validation errors, long values, a 50-row page, an open
sidebar on a phone, an open dialog, `ar`/`he` locale (RTL) and a `de` locale (long words).

## 4. Report

Write `.ux-review/<run>/report.md`. Tell the user the result first: the top 3 problems in one
line each. Then list one table row per issue, ranked:

| P | issue (user impact) | where | devices | evidence | fix |
|---|---|---|---|---|---|
| P0 | blocks a task, loses data, or fails WCAG A/AA (contrast, no label, target < 24px) | | | screenshot path, metric | |
| P1 | slows or confuses a frequent task; broken layout on a supported device | | | | |
| P2 | polish: alignment, rhythm, inconsistency, weak hierarchy | | | | |
| P3 | ideas that need a product decision | | | | |

Rules for the report:
- One row = one problem, named by its **user impact** ("Delete sits 4px from Save on phones; easy mis-tap"), not by the CSS.
- Name the false positives you threw out from `findings.json`, so the next run doesn't repeat them.
- Group problems that come from one cause (one token or one component) into one row.
- When the user asked for something to share, publish the report as an Artifact. Put the key before/after screenshots side by side in it.

In `audit` mode, stop here.

## 5. Improve (`fix` mode)

Change the design system, not single pages:

- **Tokens first.** Colour, spacing, radius, type size and target size are tokens in
  `src/hyperadmin/static/css/_tokens.css`; dark values are in `_dark-mode.css`. A contrast or
  spacing fix that changes a token fixes every page. Never hard-code a hex value or px spacing
  in a component.
- **Component CSS** lives in `static/css/_<component>.css`. The layout is mobile-first
  (`_responsive.css`), using breakpoints `--ha-bp-sm` 640 / `--ha-bp-md` 768 / `--ha-bp-lg` 1024
  / `--ha-bp-xl` 1280. Touch sizing belongs in `_accessibility.css` under `@media (pointer: coarse)`.
  Support logical properties for RTL (`margin-inline-start`, not `margin-left`).
- **Templates** are in `src/hyperadmin/templates/`. Keep the semantic HTML and ARIA. New
  interactive or testable elements get a `data-testid` named `<view>-<element>` (see CLAUDE.md).
  Text goes through `_()` for i18n.
- Keep `prefers-reduced-motion`, `forced-colors` and `prefers-contrast` working. Every visual
  change gets a dark-mode check.
- Don't redesign beyond the findings. One commit per finding or group of findings
  (`style(templates): …`, `fix(css): …`).

After the changes:

1. Re-capture into `.ux-review/after` with the same `--paths`/`--devices`. Read the after shots
   for every page you touched, on every device. A fix for phones that breaks the desktop is
   not a fix.
2. Compare `findings.json` before and after. The fixed rules must drop and nothing new may appear.
3. Add or extend Playwright E2E tests for behaviour changes (`tests/e2e/test_responsive_design.py`
   style: one BDD scenario per test, `get_by_role`/`get_by_label`/`get_by_test_id`, never
   `.ha-*` selectors). Refresh the visual baselines that the change moves (`tests/e2e/snapshots`).
   Never bypass them.
4. `uv run ruff check . && uv run ruff format --check .`, `poe lint`, `poe test:unit`, and the
   affected E2E files.
5. Open the PR with the before/after screenshot pairs for the main fixes, the ranked table, and
   manual test scenarios (device + theme + steps).

## Done when

- Every page in scope was seen on phone, tablet and desktop in both themes.
- The report ranks problems by user impact, with screenshot evidence.
- In `fix` mode: all P0/P1 issues are fixed or written up as issues; after shots and automated
  checks confirm it; tests and lint pass.
- The demo server was stopped (stop the background task).

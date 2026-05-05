---
type: story
id: mhoRScF5hYQN
title: "docs: publish hyperadmin-logfire README and link from main docs"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - size:S
  - planned
  - plugins
  - observability
estimate: null
epic_ref:
  id: Plo-enMpTWhB
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Polish the package README and link it from the main HyperAdmin docs site so
new users can discover the plugin.

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **Modified:** `plugins/hyperadmin-logfire/README.md` — full content
- **New:** `docs/plugins/logfire.md` — short page on the main docs site
- **Modified:** `mkdocs.yml` — add the page under the "Plugins" nav (the section
  added by Epic 1's `docs-plugin-author-guide-and-hook-reference` story)

## Content Outline

### `plugins/hyperadmin-logfire/README.md`
- One-paragraph pitch
- Install: `pip install hyperadmin-logfire` or `pip install hyperadmin[logfire]`
- Usage: 5-line example with `logfire.configure()` + `instrument_admin(admin)`
- What it captures: adapter spans, HTTP, SQL, validation events, auth events
- Configuration: link to Logfire docs for `logfire.configure()` options
- Disable: `Admin(disabled_plugins=["logfire"])` and env var
- Example dashboard screenshots (optional, defer if not ready)
- License: same as parent (MIT)

### `docs/plugins/logfire.md`
- Short summary + link to GitHub README
- Span / event schema reference (names + attributes)
- Comparison table: vs django-silk, vs Sentry, vs raw OpenTelemetry

## Acceptance Criteria

- [ ] Package README complete and renders correctly on PyPI
- [ ] Main-docs page renders under `/plugins/logfire/`
- [ ] `poe docs:build` succeeds
- [ ] No broken links

## Blocked by

- `test-e2e-end-to-end-spans-and-events-against-test-sink` (so docs match
  shipped behaviour)

## Parent

- Epic: `epic-plugin-logfire-first-plugin`

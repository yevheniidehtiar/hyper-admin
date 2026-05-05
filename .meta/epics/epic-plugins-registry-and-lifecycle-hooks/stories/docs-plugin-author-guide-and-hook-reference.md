---
type: story
id: RxpZ4QbslvR5
title: "docs: plugin author guide and hook reference"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - size:S
  - planned
  - plugins
estimate: null
epic_ref:
  id: um1zqB0-b2AZ
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Publish a plugin author guide and hook reference under the docs site.

**Spec:** [`docs/specs/plugin-registry.md`](../../../../docs/specs/plugin-registry.md)

## Files to Change

- **New:** `docs/plugins/index.md` — overview, installation, disable mechanism
- **New:** `docs/plugins/authoring.md` — step-by-step "your first plugin"
- **New:** `docs/plugins/hooks.md` — table of all hooks, signatures, fire timing
- **Modified:** `mkdocs.yml` — add a "Plugins" nav section

## Content Outline

### `docs/plugins/index.md`
- What HyperAdmin plugins are
- How to install (`pip install hyperadmin-foo`)
- How to disable (`Admin(disabled_plugins=...)`, env var)
- How to introspect (`hyperadmin plugins list`)

### `docs/plugins/authoring.md`
- Minimal plugin (5-line example with `Plugin` Protocol)
- Declaring the entry point in `pyproject.toml`
- Implementing `on_register`
- Adding a hook handler (with the `name` attribute requirement)
- Testing a plugin (using `monkeypatch` on `entry_points`)
- Common pitfalls (per-request state, sync-only contract, exception isolation)

### `docs/plugins/hooks.md`
- Full hook reference table from SDD `### API / Protocol Changes` section
- Fire timing: when, from which module, in what order
- Hook ordering between plugins: alphabetical by entry-point name
- Synchronous contract: hooks run in the request flow

## Acceptance Criteria

- [ ] All three doc pages published
- [ ] `mkdocs.yml` nav updated
- [ ] `poe docs:build` succeeds
- [ ] `poe docs:serve` renders the new section locally
- [ ] Internal links between pages work (no 404s)

## Blocked by

- `test-e2e-plugin-hook-firing-and-failure-isolation` (so docs match the
  shipped behaviour, not the SDD draft)

## Parent

- Epic: `epic-plugins-registry-and-lifecycle-hooks`

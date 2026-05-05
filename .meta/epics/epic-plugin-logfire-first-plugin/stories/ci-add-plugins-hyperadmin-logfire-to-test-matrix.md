---
type: story
id: 7fh6lg_zbkke
title: "ci: add plugins/hyperadmin-logfire to test matrix"
status: todo
priority: medium
assignee: null
labels:
  - ci
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

Run lint + unit + e2e for `plugins/hyperadmin-logfire` in CI on every PR.
Publish to TestPyPI on tag push, real PyPI on manual workflow dispatch.

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **Modified:** `.github/workflows/test.yml` — add `plugins/hyperadmin-logfire`
  to the matrix entry that runs `poe lint && poe test:unit`. Add an extra E2E
  job step that targets the plugin's E2E suite specifically.
- **New:** `.github/workflows/publish-hyperadmin-logfire.yml` — workflow that
  builds and publishes the package to TestPyPI on `v*` tag, real PyPI on manual
  dispatch with explicit version input.

## Acceptance Criteria

- [ ] Plugin lint + unit + E2E run on every PR
- [ ] CI fails if any of the plugin tests fail (no exclusion via `continue-on-error`)
- [ ] TestPyPI publish workflow tested on a pre-release tag (`v0.1.0a1` or similar)
- [ ] Real PyPI workflow gated behind manual dispatch with confirmation
- [ ] Publishing uses Trusted Publishing (OIDC), no long-lived tokens

## Blocked by

- `chore-scaffold-pluginshyperadmin-logfire-package`

## Parent

- Epic: `epic-plugin-logfire-first-plugin`

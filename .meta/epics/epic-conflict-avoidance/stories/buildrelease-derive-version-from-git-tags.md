---
type: story
id: st-conflict-02
title: "build(release): derive version from git tags"
status: todo
priority: medium
assignee: null
labels:
  - size:S
  - planned
  - area:packaging
  - layer:packaging
estimate: null
epic_ref:
  id: ep-conflict-avoidance-01
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

Release PRs edit `version = ...` in `pyproject.toml` (v0.5.8 #643 bumps it by hand), so every release conflicts
with any open PR that touches `pyproject.toml`. Make the version dynamic: `hatch-vcs` reads it from the `v*` git tag
at build time, `[project] dynamic = ["version"]`, and commitizen switches to `version_provider = "scm"` so `cz bump`
only tags and writes the changelog. Release PRs stop editing `pyproject.toml`.

Wait for v0.5.8's release story (st-v058-byoa-50) — it owns `pyproject.toml` and the release workflow until then.

## Files to Change

- `pyproject.toml` — `dynamic = ["version"]`, `hatch-vcs` in `[build-system].requires`, `[tool.hatch.version]`
  `source = "vcs"`, `[tool.commitizen] version_provider = "scm"`
- `uv.lock` — regenerated with `uv lock`
- `.github/workflows/release.yml` — tag-only bump; checkout with `fetch-depth: 0`
- `.github/workflows/publish.yml` — build from the tag with full history
- `docs/contributing.md` — fill the `### Releases` stub only

## Scenarios

```
Scenario: Built wheel carries the tag version
  Given HEAD is tagged v0.6.0
  When  `uv build` runs
  Then  the wheel metadata version is 0.6.0

Scenario: Untagged build gets a dev version
  Given HEAD is 3 commits after v0.6.0
  When  `uv build` runs
  Then  the version is a PEP 440 dev version after 0.6.0

Scenario: Release does not edit pyproject.toml
  Given the release workflow runs `cz bump`
  When  it finishes
  Then  only CHANGELOG.md changes and a new tag is pushed
```

## Acceptance Criteria

- [ ] Built wheel carries the tag version
- [ ] Untagged build gets a dev version
- [ ] Release does not edit pyproject.toml
- [ ] `importlib.metadata.version("hyperadmin")` matches the tag in an installed build
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `builddeps-one-lane-dependency-policy-uv-lock-regeneration-c` (st-conflict-01) — creates the `docs/contributing.md` stub
- `buildrelease-0-5-0a1-pep440-commitizen-version-and-fixed-rel` (st-v058-byoa-50)

## Parent

- Epic: `epic-conflict-avoidance`

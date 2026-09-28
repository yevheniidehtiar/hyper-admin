---
type: story
id: st-v058-byoa-50
title: "build(release): 0.5.0a1, pep440 commitizen, __version__ and fixed release/publish workflows"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:packaging
  - layer:packaging
  - needs-human
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Set the version to `0.5.0a1` with commitizen `version_scheme='pep440'` and `major_version_zero=true`, and expose `__version__` via `importlib.metadata`. Change `publish.yml` to trigger on `release: published`, with a build, twine check and wheel smoke test followed by a trusted-publishing job. Fix `release.yml` to push to `master` and run `gh release create --prerelease`. Update the README and getting-started install lines. The owner must configure the PyPI trusted publisher first (Owner decision 5).

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: E

## Files to Change

- `pyproject.toml`
- `src/hyperadmin/__init__.py`
- `.github/workflows/publish.yml`
- `.github/workflows/release.yml`
- `README.md`
- `docs/getting-started.md`
- `CHANGELOG.md`

## Scenarios

```
Scenario: version exposed
  Given hyperadmin installed
  When  hyperadmin.__version__ is read
  Then  it equals the pyproject version

Scenario: smoke test before upload
  Given a published GitHub release
  When  publish.yml runs
  Then  the build job imports hyperadmin from the built wheel before the publish job starts

Scenario: draft releases do not publish
  Given a draft GitHub release
  When  it is created
  Then  publish.yml does not run
```

## Acceptance Criteria

- [ ] version exposed
- [ ] smoke test before upload
- [ ] draft releases do not publish
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `build-commit-uv-lock-enforce-uv-sync-locked-in-ci-and-gate-p` (st-v058-byoa-12)
- `builddeps-lift-the-sqlmodel-0-0-45-cap-and-migrate-examples` (st-v058-byoa-48)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)

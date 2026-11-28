# Contributing to HyperAdmin

Thanks for your interest in contributing! This document covers the process for contributing to this project.

## Development setup

```bash
# Clone the repo
git clone https://github.com/yevheniidehtiar/hyper-admin.git
cd hyper-admin

# Install uv (https://docs.astral.sh/uv/), then set up the dev environment
uv sync --all-extras
uv run pre-commit install
```

Tasks run through [Poe the Poet](https://poethepoet.natn.io/), which is installed
with the dev dependencies. Use `uv run poe <task>`, or `poe <task>` inside the
activated virtual environment.

## Branches

| Branch | Purpose |
|--------|---------|
| `develop` | Integration branch. Pull requests from contributors target it. |
| `master` | Released code. Updated only by the maintainer at release time. |

## Workflow

1. Fork the repo and create a feature branch from `develop`
2. Make your changes
3. Run quality checks: `poe lint && poe test:unit`
4. Commit using [conventional commits](https://www.conventionalcommits.org/):
   - `feat:` — new feature
   - `fix:` — bug fix
   - `docs:` — documentation only
   - `chore:` — maintenance tasks
   - `refactor:` — code restructuring without behavior change
5. Open a pull request against `develop`

## Merge hygiene

- Pull requests are merged by **rebase**. Squash and merge commits are disabled,
  so every commit on your branch lands on `develop` as is. Keep each commit
  meaningful and in conventional-commit format.
- Rebase on the latest `develop` before opening the PR and again if it falls
  behind. Do not merge `develop` into your branch.
- Keep a PR to one topic. Do not stack PRs on top of each other.
- Every PR to `develop` needs an approving review from the maintainer, green CI,
  and all review threads resolved.
- New and changed lines must be covered by tests (`poe test:cov-diff`).

## Code style

- **Linter/formatter**: ruff (runs via `poe lint`)
- **Type hints**: required on all public functions
- **Docstrings**: required on all public modules, classes, and functions
- **Tests**: required for all new functionality

## Public API snapshot

`tests/unit/test_public_api.py` records the public API (as defined in
[Versioning & Deprecation](docs/versioning.md#what-is-public-api)) in
`tests/unit/public_api_snapshot.txt`: the names in `hyperadmin.__all__` and its lazy exports,
every `hyperadmin` name the docs import or reference, their signatures and public members, the
`HyperAdminSettings` fields, the plugin contract and the `hyperadmin` CLI options. It also checks
that each of these names has a docstring, full type annotations, an entry under `docs/api/` and
at least one test.

When you change the public API on purpose, regenerate the snapshot and commit it with the change:

```bash
HYPERADMIN_UPDATE_API_SNAPSHOT=1 uv run pytest tests/unit/test_public_api.py
```

The regeneration run writes the file and then fails, so read the diff before you rerun the test.

## Pull request checklist

- [ ] `poe lint` passes
- [ ] `poe test:unit` passes
- [ ] New public API has docstrings, a `docs/api/` entry and an updated API snapshot
- [ ] `poe docs:build` reports no issues (if docs changed)
- [ ] Tests cover the new/changed behavior
- [ ] CHANGELOG.md updated (if user-facing change)

## Reporting issues

Use [GitHub Issues](https://github.com/yevheniidehtiar/hyper-admin/issues) with these templates:

- **Bug report** — include reproduction steps, expected vs actual behavior
- **Feature request** — describe the use case and proposed solution

## Code of conduct

Be respectful, constructive, and inclusive. We're all here to build something useful.

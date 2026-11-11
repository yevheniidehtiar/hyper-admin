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
| `epic/<slug>` | One branch per epic, used by the project's automation. Story PRs merge into it, and the epic lands on `develop` as a single reviewed PR. Do not target these branches unless a maintainer asks you to. |

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

## Merge hygiene

Parallel PRs are merged by rebase only, so every conflict costs a rebase. Keep PRs small and additive.

### Dependencies

Dependency, extra and version changes ship in their **own small PR**, never bundled into a feature PR.

Never hand-merge `uv.lock`. CI runs `uv lock --check` and fails when the committed lock differs from what
`uv lock` produces. On a lock conflict:

```bash
git fetch origin develop
git checkout origin/develop -- uv.lock   # take develop's lock
git rebase origin/develop
uv lock                                  # regenerate against your pyproject.toml
git add uv.lock && git commit -m "build(deps): regenerate uv.lock"
```

### Releases

Release process notes are added here.

### Story status

Story status tracking notes are added here.

### Conflicting PRs

Handling of conflicting PRs is described here.

## Code style

- **Linter/formatter**: ruff (runs via `poe lint`)
- **Type hints**: required on all public functions
- **Docstrings**: required on all public modules, classes, and functions
- **Tests**: required for all new functionality

## Pull request checklist

- [ ] `poe lint` passes
- [ ] `poe test:unit` passes
- [ ] New public API has docstrings
- [ ] Tests cover the new/changed behavior
- [ ] CHANGELOG.md updated (if user-facing change)

## Reporting issues

Use [GitHub Issues](https://github.com/yevheniidehtiar/hyper-admin/issues) with these templates:

- **Bug report** — include reproduction steps, expected vs actual behavior
- **Feature request** — describe the use case and proposed solution

## Code of conduct

Be respectful, constructive, and inclusive. We're all here to build something useful.

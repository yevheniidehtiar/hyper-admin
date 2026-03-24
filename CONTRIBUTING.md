# Contributing to HyperAdmin

Thanks for your interest in contributing! This document covers the process for contributing to this project.

## Development setup

```bash
# Clone the repo
git clone https://github.com/yevheniidehtiar/hyper-admin.git
cd hyper-admin

# Install just (task runner) — https://github.com/casey/just
# Then bootstrap the dev environment
just bootstrap
```

## Workflow

1. Fork the repo and create a feature branch from `main`
2. Make your changes
3. Run quality checks: `just lint && just test`
4. Commit using [conventional commits](https://www.conventionalcommits.org/):
   - `feat:` — new feature
   - `fix:` — bug fix
   - `docs:` — documentation only
   - `chore:` — maintenance tasks
   - `refactor:` — code restructuring without behavior change
5. Open a pull request against `main`

## Code style

- **Linter/formatter**: ruff (runs via `just lint`)
- **Type hints**: required on all public functions
- **Docstrings**: required on all public modules, classes, and functions
- **Tests**: required for all new functionality

## Pull request checklist

- [ ] `just lint` passes
- [ ] `just test` passes
- [ ] New public API has docstrings
- [ ] Tests cover the new/changed behavior
- [ ] CHANGELOG.md updated (if user-facing change)

## Reporting issues

Use [GitHub Issues](https://github.com/yevheniidehtiar/hyper-admin/issues) with these templates:
- **Bug report** — include reproduction steps, expected vs actual behavior
- **Feature request** — describe the use case and proposed solution

## Code of conduct

Be respectful, constructive, and inclusive. We're all here to build something useful.

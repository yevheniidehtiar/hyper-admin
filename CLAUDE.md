# HyperAdmin

Pydantic-native admin interface for FastAPI, powered by HTMX. Python package at `src/hyperadmin/`.

## Stack

- **Backend**: FastAPI + SQLModel/SQLAlchemy + Pydantic v2
- **Frontend**: HTMX + Alpine.js + custom CSS (`ha-*` design system) + Jinja2 templates
- **Package manager**: uv (NOT pip, NOT poetry)
- **Task runner**: poethepoet (`poe`)
- **Tests**: pytest (unit) + Playwright (E2E)
- **Linting**: ruff + mypy via pre-commit
- **Docs**: MkDocs with Material theme

## Commands

```bash
poe lint              # Run all linters (pre-commit hooks: ruff, mypy, commitizen)
poe test              # Run all tests (unit + e2e)
poe test:unit         # Unit tests only (pytest with coverage)
poe test:e2e          # E2E tests with Playwright
poe docs:serve        # Serve docs locally on port 8080
poe docs:build        # Build documentation
uv sync --all-extras  # Install all dependencies
uv run <cmd>          # Run commands in the virtual environment
```

## Branch and Commit Conventions

- **Main branch**: `master`
- **Branch naming**: `issue-<number>` for issue-linked work
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) (enforced by commitizen pre-commit hook)
- **Include issue number**: `feat: description (#42)`

## Constraints

- Do NOT manipulate `.venv` manually; use `uv run` to execute commands
- Do NOT break existing tests
- Do NOT expand scope without explicit approval
- Do NOT leave commented-out code in the codebase
- Check `ROADMAP.md` before starting major work to confirm priority and scope

## Rules

- @.claude/rules/code-style.md
- @.claude/rules/testing.md
- @.claude/rules/git-workflow.md

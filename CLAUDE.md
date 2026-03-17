# HyperAdmin

Pydantic-native admin interface for FastAPI, powered by HTMX. Python package at `src/hyperadmin/`.

## Stack

- **Backend**: FastAPI + SQLModel/SQLAlchemy + Pydantic v2
- **Frontend**: HTMX + Alpine.js + Tailwind CSS + Flowbite + Jinja2 templates
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
poe static:build-css  # Build Tailwind CSS via Docker
uv sync --all-extras  # Install all dependencies
uv run <cmd>          # Run commands in the virtual environment
```

## Branch and Commit Conventions

- **Main branch**: `master`
- **Branch naming**: `issue-<number>` for issue-linked work
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) (enforced by commitizen pre-commit hook)
- **Include issue number**: `feat: description (#42)`

## Code Conventions

- Group by feature: `src/hyperadmin/<feature>/` (e.g., `adapters/`, `views/`, `core/`)
- Name files by implementation: `adapters/sqlmodel.py` not `sqlmodel_adapter.py`
- Type hints required on all functions and methods
- Line length: 100 characters
- No commented-out code, no `pass`/`TODO` placeholders in final code
- Handle API errors via `fastapi.HTTPException` with clear messages
- Use SQLModel for data models, Pydantic for validation
- Optimize DB access with `selectinload()` for relationships; add pagination for large collections
- Use HTMX for server interactions, Alpine.js for client-side behavior

## Testing

- **TDD**: Write a failing test first, implement to pass, then refactor
- **Unit tests**: `tests/unit/`
- **E2E tests**: `tests/e2e/` (Playwright)
- Always run `poe lint` and `poe test` before submitting changes
- Target near 99% coverage for new code

## Constraints

- Do NOT manipulate `.venv` manually; use `uv run` to execute commands
- Do NOT break existing tests
- Do NOT expand scope without explicit approval
- Do NOT leave commented-out code in the codebase
- Check `ROADMAP.md` before starting major work to confirm priority and scope

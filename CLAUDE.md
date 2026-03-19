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
poe deps:bump         # Bump deps and verify across compatibility matrix
poe docs:serve        # Serve docs locally on port 8080
poe docs:build        # Build documentation
uv sync --all-extras  # Install all dependencies
uv run <cmd>          # Run commands in the virtual environment
```

## Dependency Management

HyperAdmin is a library consumed by other projects, so dependency bounds matter:

- **Runtime deps** (`[project.dependencies]`): Keep conservative lower bounds (e.g., `pydantic>=2.7`). Only bump when code requires a newer API or a security fix exists.
- **Dev deps** (`[project.optional-dependencies].dev`): Bump freely to latest — they only affect contributors.
- **Dependabot**: Configured for monthly automated dev dep bumps via PR.

### Bumping Dependencies

```bash
poe deps:bump         # Bump lock file and verify across compatibility matrix
```

This command:
1. Runs `uv lock --upgrade` to resolve latest compatible versions
2. Verifies lint + unit tests + security checks across 3 combos:
   - Python 3.10 + lowest-direct
   - Python 3.13 + lowest-direct
   - Python 3.13 + highest
3. Restores the default environment when done (even on failure)

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

### E2E Prerequisites

`poe test:e2e` installs the Chromium browser automatically. Running `pytest tests/e2e/` directly requires the browser to be installed first:

```bash
uv run playwright install chromium
```

### CSS Class Convention in E2E Tests

Templates use custom `ha-*` CSS classes (not raw Tailwind utilities). Use these class names in Playwright selectors:

| Element | Class |
|---------|-------|
| `body` | `ha-page` |
| `nav` | `ha-navbar` |
| `aside` | `ha-sidebar` |
| `main` | `ha-content` |
| Validation error list | `ha-field-errors` |

When templates change class names, update the corresponding E2E selectors to match.

## Constraints

- Do NOT manipulate `.venv` manually; use `uv run` to execute commands
- Do NOT break existing tests
- Do NOT expand scope without explicit approval
- Do NOT leave commented-out code in the codebase
- Check `ROADMAP.md` before starting major work to confirm priority and scope

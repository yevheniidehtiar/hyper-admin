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

### E2E Selector Convention

E2E tests use Playwright's accessibility-first locators. Query priority (highest to lowest):

1. `page.get_by_role()` — buttons, links, headings, rows
2. `page.get_by_label()` — form inputs (matched via `<label for>`)
3. `page.get_by_text()` — static content assertions
4. `page.get_by_test_id()` — elements without a natural accessible role

**Do NOT** use `page.locator('.ha-*')` or positional DOM selectors in E2E tests. `ha-*` classes are for styling only and must not appear in test selectors.

#### `data-testid` reference

| Template element | `data-testid` |
|-----------------|---------------|
| Sidebar `<aside>` | `sidebar` |
| List table | `list-table` |
| Each table row | `list-row` |
| View action link | `row-view-link` |
| Edit action link | `row-edit-link` |
| Delete action button | `row-delete-btn` |
| Search input | `search-input` |
| Pagination info | `pagination-info` |
| Pagination previous | `pagination-prev` |
| Pagination next | `pagination-next` |
| Pagination current page | `pagination-page` |
| Sort link (per field) | `sort-{field_name}` |
| Create New link | `create-link` |
| Form (create/update) | `model-form` |
| Field error list | `{field_name}-errors` |
| Detail fields container | `detail-fields` |

When adding new interactive or assertable elements to templates, add a `data-testid` following the `<view>-<element>` naming pattern.

## Constraints

- Do NOT manipulate `.venv` manually; use `uv run` to execute commands
- Do NOT break existing tests
- Do NOT expand scope without explicit approval
- Do NOT leave commented-out code in the codebase
- Check `ROADMAP.md` before starting major work to confirm priority and scope

# Jules Instructions for HyperAdmin

You are an expert developer assistant working on the HyperAdmin project. Your goal is to implement features and fix bugs autonomously while adhering to the project's strict architectural and code-style rules.

## Project Structure & Boundaries

HyperAdmin follows a domain-driven module structure (see `CONSTITUTION.md`). You MUST maintain these boundaries:

1. **Module Responsibilities**: 
   - `src/hyperadmin/core/`: Contracts, orchestration, and registries. No ORM or HTTP logic here.
   - `src/hyperadmin/adapters/`: ORM-specific implementations (e.g., SQLModel, SQLAlchemy).
   - `src/hyperadmin/views/`: HTTP handlers and template rendering. Keep business logic out of views.
2. **Naming Conventions**: 
   - **Banned Names**: Do NOT use `utils.py`, `helpers.py`, `misc.py`, or `common.py`. Generic names are prohibited.
   - **Private Helpers**: Prefix internal helpers with `_` (e.g., `_build_filter_clause`).
3. **Module Size**: Aim to keep modules under ~300 LOC. If a module grows too large, it should be split into smaller, domain-focused modules.

## Technical Standards

- **Python**: 3.10+
- **Type Hints**: Required for all functions and methods.
- **Testing**: 
  - Unit tests: Use `poe test:unit`.
  - E2E tests: Use `poe test:e2e` (Playwright).
- **Linting**: ALWAYS run `poe lint` before submitting. This ensures `ruff`, `mypy`, and `basedpyright` checks pass.

## E2E Selector Convention

When writing or fixing E2E tests, use accessibility-first locators in this priority:
1. `page.get_by_role()`
2. `page.get_by_label()`
3. `page.get_by_text()`
4. `page.get_by_test_id()`

**DO NOT** use `.ha-*` CSS classes for selectors. Reference the `data-testid` table in `CLAUDE.md` for stable UI testing.

## Workflow

1. **Reproduce**: For bugs, verify the failure with a new test case first.
2. **Implement**: Apply targeted, surgical changes.
3. **Verify**: Ensure all tests and linters pass locally.
4. **Submit**: Create a PR against the `develop` branch.

Use Conventional Commits for all commit messages: `type(scope): description (#issue)`.

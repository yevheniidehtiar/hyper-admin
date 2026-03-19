# Gemini AI Context for HyperAdmin

This file provides context and instructions for AI agents interacting with the HyperAdmin project.

## Project Overview

**HyperAdmin** is a modern, Pydantic-native admin interface framework for **FastAPI**, powered by **HTMX**. It is designed to quickly create rich, data-driven admin panels directly from data models with minimal JavaScript. 

**Key Technologies:**
- Python (>=3.10)
- FastAPI
- Pydantic
- HTMX (for dynamic UI)
- SQLModel & SQLAlchemy (Database integration)
- Jinja2 (Templating)

## Building and Running

The project uses `uv` for fast dependency management and `poe` (poethepoet) as a task runner.

### Key Commands
- **Install Dependencies:** `uv sync --all-extras`
- **Run commands in virtual env:** `uv run <cmd>`
- **Linting:** `poe lint` (Runs ruff, mypy, commitizen pre-commit hooks)
- **Testing:**
  - All tests: `poe test`
  - Unit tests: `poe test:unit`
  - E2E tests: `poe test:e2e`
- **Dependencies:** `poe deps:bump` (Bumps lock file and verifies across compatibility matrix)
- **Documentation:** `poe docs:serve` (serve locally) and `poe docs:build`

## Development Conventions

### Architecture & Module Boundaries
Refer to `CONSTITUTION.md` and `AGENTS.md` for strict architectural guidelines:
- Modules must have a single, named responsibility mapping to a domain concept.
- **Banned Filenames:** Do not use `utils.py`, `helpers.py`, `misc.py`, or `common.py`.
- **Nesting Limit:** Do not exceed two levels of nesting unless explicitly justified.
- **Dependency Direction:** 
  - `core/` must NOT import from `views/` or `adapters/`.
  - `adapters/` must NOT import from `views/`.
  - No circular imports between top-level modules.

### Testing Conventions
- **E2E Testing (Playwright):** Strict use of accessibility-first locators is required.
  - **Priority:** `get_by_role()` > `get_by_label()` > `get_by_text()` > `get_by_test_id()`.
  - **Prohibited:** Do NOT use `page.locator('.ha-*')` or positional DOM selectors. `ha-*` classes are for styling only.
  - Refer to `CLAUDE.md` for the standard `data-testid` reference list.

### Dependency Management
- **Runtime Dependencies:** Keep conservative lower bounds. Only bump when new APIs or security fixes are needed.
- **Dev Dependencies:** Can be bumped freely to the latest versions.
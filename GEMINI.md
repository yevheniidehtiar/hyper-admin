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

### Setup (MUST run first)
```bash
uv sync --all-extras
uv run pre-commit install  # installs commit-msg, pre-commit, AND pre-push hooks
```

### Key Commands
- **Run commands in virtual env:** `uv run <cmd>`
- **Linting:** `uv run poe lint`
- **Testing:**
  - Unit tests: `uv run poe test:unit`
  - E2E tests: `uv run poe test:e2e`
- **Dependencies:** `uv run poe deps:bump`
- **Documentation:** `uv run poe docs:serve` / `uv run poe docs:build`

## MANDATORY: Pre-Push Verification

**You MUST run the following checks before every push. Do NOT skip them. Do NOT assume they pass. Do NOT report success without actually running the commands and verifying zero exit codes.**

### Step 1: Lint (ruff check + ruff format + mypy + basedpyright)
```bash
uv run poe lint
```
This runs `pre-commit run --all-files` which executes:
- `ruff check` — linting rules (import sorting, unused imports, code style, etc.)
- `ruff format` — code formatting
- `mypy` — type checking
- `basedpyright` — strict type checking

**If `uv run poe lint` fails:** fix ALL reported errors, then re-run until it passes with exit code 0. Do NOT commit or push until lint is fully green.

### Step 2: Unit tests
```bash
uv run poe test:unit
```
**If tests fail:** fix the failures, then re-run lint (step 1) AND tests again.

### Step 3: Only then commit and push
```bash
git add <files>
git commit -m "type(scope): description (#issue)"
git push
```

### What "passing" means
- Exit code 0 from `uv run poe lint`
- Exit code 0 from `uv run poe test:unit`
- You must actually run these commands and see the output — do NOT hallucinate or assume results.

### Common ruff errors and fixes
- **F401** (unused import): Remove the import.
- **I001** (import sorting): Let `ruff format` or `ruff check --fix` handle it, or sort manually: stdlib → third-party → local, each group alphabetical.
- **E501** (line too long): Line limit is 100 chars. Break long lines.
- **UP** (pyupgrade): Use modern Python syntax (e.g., `X | Y` instead of `Union[X, Y]`).
- **RUF** rules: Check https://docs.astral.sh/ruff/rules/ for specifics.

## Commit Message Format

Follow Conventional Commits (enforced by commitizen):
```
type(optional-scope): description (#issue-number)
```
Valid types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`

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

### Code Style
- Type hints required on all functions and methods.
- Line length: 100 characters.
- No commented-out code, no `pass`/`TODO` placeholders in final code.
- Use `from __future__ import annotations` is NOT used — use runtime-valid type syntax.

### Testing Conventions
- **E2E Testing (Playwright):** Strict use of accessibility-first locators is required.
  - **Priority:** `get_by_role()` > `get_by_label()` > `get_by_text()` > `get_by_test_id()`.
  - **Prohibited:** Do NOT use `page.locator('.ha-*')` or positional DOM selectors. `ha-*` classes are for styling only.
  - Refer to `CLAUDE.md` for the standard `data-testid` reference list.

### Dependency Management
- **Runtime Dependencies:** Keep conservative lower bounds. Only bump when new APIs or security fixes are needed.
- **Dev Dependencies:** Can be bumped freely to the latest versions.

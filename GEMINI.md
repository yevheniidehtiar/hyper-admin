# HyperAdmin — Gemini CLI Instructions

## Project Overview

A modern, Pydantic-native admin interface for FastAPI, powered by HTMX.

**Language:** python | **Repo:** https://github.com/yevheniidehtiar/hyper-admin

**Key Technologies:**
- Python (>=3.10)
- FastAPI
- Pydantic
- HTMX (for dynamic UI)
- SQLModel & SQLAlchemy (Database integration)
- Jinja2 (Templating)

## Development Commands

```bash
just lint    # lint
just test    # test
just build   # build
just docs    # docs
```

## Gemini CLI Conventions

- Use `gemini -p` for one-shot tasks, interactive mode for exploration
- Always verify generated code with `just lint && just test`
- Prefer reading existing patterns before generating new code
- Use `@file` syntax to ground context: `gemini "@src/main.py explain this"`
- Reserve Gemini CLI for size:S tasks (< 30 min effort) — quick fixes, config changes, utility functions

## Architecture Notes

Refer to `CONSTITUTION.md` and `AGENTS.md` for strict architectural guidelines:
- Modules must have a single, named responsibility mapping to a domain concept.
- **Banned Filenames:** Do not use `utils.py`, `helpers.py`, `misc.py`, or `common.py`.
- **Nesting Limit:** Do not exceed two levels of nesting unless explicitly justified.
- **Dependency Direction:**
  - `core/` must NOT import from `views/` or `adapters/`.
  - `adapters/` must NOT import from `views/`.
  - No circular imports between top-level modules.

## Code Style
- Type hints required on all functions and methods.
- Line length: 100 characters.
- No commented-out code, no `pass`/`TODO` placeholders in final code.
- Use `from __future__ import annotations` is NOT used — use runtime-valid type syntax.

## Testing Conventions
- **E2E Testing (Playwright):** Strict use of accessibility-first locators is required.
  - **Priority:** `get_by_role()` > `get_by_label()` > `get_by_text()` > `get_by_test_id()`.
  - **Prohibited:** Do NOT use `page.locator('.ha-*')` or positional DOM selectors. `ha-*` classes are for styling only.
  - Refer to `CLAUDE.md` for the standard `data-testid` reference list.

## Dependency Management
- **Runtime Dependencies:** Keep conservative lower bounds. Only bump when new APIs or security fixes are needed.
- **Dev Dependencies:** Can be bumped freely to the latest versions.

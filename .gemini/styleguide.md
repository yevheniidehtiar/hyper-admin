# HyperAdmin Style Guide for Jules

## CRITICAL: Verification Before Push

**Every push MUST be preceded by successful lint and test runs. This is non-negotiable.**

### Required verification sequence

```bash
# 1. Install dependencies and git hooks (MUST run on every fresh clone)
uv sync --all-extras
uv run pre-commit install  # installs commit-msg, pre-commit, AND pre-push hooks

# 2. Run ALL linters (ruff check, ruff format, mypy, basedpyright)
uv run poe lint

# 3. Run unit tests
uv run poe test:unit
```

### Rules

1. You MUST run `uv run poe lint` after ALL code changes and before committing.
2. You MUST verify the command exits with code 0.
3. If it fails, fix every error it reports, then re-run until clean.
4. You MUST run `uv run poe test:unit` after lint passes.
5. If tests fail, fix failures, then re-run lint AND tests.
6. Do NOT commit or push until BOTH commands pass with exit code 0.
7. Do NOT report that checks pass without actually running them.
8. Do NOT use `--no-verify` or skip any hooks.

### What `uv run poe lint` actually runs

It executes `pre-commit run --all-files` which runs these hooks in order:
- `ruff check --force-exclude --extend-fixable=F401,F841 --fix-only` (auto-fixes some issues)
- `ruff format --force-exclude` (formats code)
- `mypy src` (type checking)
- `basedpyright src` (strict type checking)

After auto-fixes from ruff, you may need to re-stage and re-run.

### If ruff check fails

Run `uv run ruff check src tests --output-format=full` to see detailed errors, then fix them manually. Common issues:
- **F401**: Unused import — remove it
- **I001**: Import not sorted — reorder: stdlib, then third-party, then local
- **E501**: Line > 100 chars — break the line
- **UP**: Use modern Python syntax (`X | Y` not `Union[X, Y]`)
- **ERA001**: Commented-out code — remove it
- **RUF**: See https://docs.astral.sh/ruff/rules/

### If mypy or basedpyright fails

- Add type annotations to all function parameters and return types
- Do not use `Any` unless absolutely necessary
- Use `from __future__ import annotations` is NOT a pattern in this project

## Code Conventions

- Line length: 100 characters
- Type hints on all functions and methods
- No commented-out code
- No `pass` or `TODO` placeholders in final code
- No `utils.py`, `helpers.py`, `misc.py`, or `common.py` filenames

## Commit Messages

Conventional Commits format (enforced by commitizen hook):
```
type(scope): description (#issue-number)
```
Valid types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`

## Testing

- Unit tests in `tests/unit/`
- E2E tests in `tests/e2e/` use Playwright with accessibility-first locators
- Use `get_by_role()`, `get_by_label()`, `get_by_text()`, `get_by_test_id()` — never CSS class selectors

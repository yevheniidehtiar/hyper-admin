---
description: Run linter and auto-fix
---
Run `uv run poe lint` and report results. If there are errors, attempt to fix them automatically,
then re-run `uv run poe lint` to confirm clean. Finish with `uv run ruff check . && uv run ruff format --check .`,
which is what CI runs.

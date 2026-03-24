---
description: Scaffold a new module or feature
---
Ask the user: what module/feature name, and what it should do.
Then generate the appropriate files following existing patterns in `src/`.
Include:
- Source module with type hints and docstrings
- Corresponding test file in `tests/`
- Update `__init__.py` exports if needed
Run `just lint` after generation.

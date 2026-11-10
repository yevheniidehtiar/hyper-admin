---
description: Run test suite with coverage
---
Run `uv run poe test:unit` (coverage is enabled by the pytest config), then `uv run poe test:cov-diff` to check
that every changed line is covered. Report failing tests with full tracebacks.
Suggest fixes for failures but do not auto-apply without confirmation.

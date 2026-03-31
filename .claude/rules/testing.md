---
paths:
  - "tests/**"
  - "src/hyperadmin/**/*.py"
---

## Testing

- **TDD**: Write a failing test first, implement to pass, then refactor
- **Unit tests**: `tests/unit/`
- **E2E tests**: `tests/e2e/` (Playwright)
- Always run `poe lint` and `poe test` before submitting changes
- Target near 99% coverage for new code

### E2E Prerequisites

`poe test:e2e` installs the Chromium browser automatically. Running `pytest tests/e2e/` directly requires:

```bash
uv run playwright install chromium
```

### E2E Selectors

For the selector priority and `data-testid` reference, see `CLAUDE.md` → E2E Selector Convention.

`ha-*` CSS classes are for **styling only** — do not use them in Playwright selectors.
Use accessibility-first locators (`get_by_role`, `get_by_label`, `get_by_text`, `get_by_test_id`).

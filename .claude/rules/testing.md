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

### CSS Class Convention in E2E Tests

Templates use custom `ha-*` CSS classes (not raw Tailwind utilities). Use these in Playwright selectors:

| Element | Class |
|---------|-------|
| `body` | `ha-page` |
| `nav` | `ha-navbar` |
| `aside` | `ha-sidebar` |
| `main` | `ha-content` |
| Validation error list | `ha-field-errors` |

When templates change class names, update the corresponding E2E selectors to match.

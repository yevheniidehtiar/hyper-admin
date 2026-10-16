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

### Coverage: 100% of changed lines (mandatory)

Every line a PR adds or changes under `src/` must be covered by unit tests. Codecov enforces
this on every PR (`codecov.yml`: patch target 100%, project total may not drop).

- Before every push, run `uv run poe test:cov-diff` (after `/usr/bin/git fetch origin`). It runs the
  unit suite and fails unless `diff-cover` reports 100% for the diff against `origin/develop`.
- A missing line means a missing test: add a behavioural test (with a Scenario docstring) for
  that branch. Do not add `# pragma: no cover` to reach the number. The only accepted
  exclusions are those in `[tool.coverage.report] exclude_lines` (`if TYPE_CHECKING:` blocks,
  `raise NotImplementedError`). Adding a new exclusion pattern needs reviewer approval.
- E2E tests do not count towards coverage; code reached only through the browser still needs a
  unit or integration test.
- Report the `test:cov-diff` result in the PR's test plan.

### E2E Prerequisites

`poe test:e2e` installs the Chromium browser automatically. Running `pytest tests/e2e/` directly requires:

```bash
uv run playwright install chromium
```

### E2E Selectors

For the selector priority and `data-testid` reference, see `CLAUDE.md` → E2E Selector Convention.

`ha-*` CSS classes are for **styling only** — do not use them in Playwright selectors.
Use accessibility-first locators (`get_by_role`, `get_by_label`, `get_by_text`, `get_by_test_id`).

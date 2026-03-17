Implement a new feature for HyperAdmin following TDD and the Assembly First approach.

## Instructions

### 1. Preparation
- Check `ROADMAP.md` to confirm the feature's priority and scope
- Create a GitHub issue if one doesn't exist: `gh issue create`
- Create a branch: `git checkout -b issue-<ID>`

### 2. Skeleton First (E2E)
- Write a failing Playwright E2E test in `tests/e2e/` that asserts the feature's UI or endpoint exists
- Implement the minimal code (route, empty template, Pydantic model) to make the test pass existence checks
- Verify: `poe test:e2e`

### 3. Data Flow & Logic (TDD Loop)
For each component (adapter, view, form):
- Write a failing unit test in `tests/unit/`
- Implement the minimal code to pass the test
- Refactor for clarity, ensure strict type hints
- Verify: `poe test`

### 4. Polish & UI
- Style using `ha-*` CSS classes from `hyperadmin.css` — no Tailwind, no inline styles
- Use existing classes: `ha-form-group`, `ha-input`, `ha-btn`, `ha-table`, etc. (see `docs/frontend/overview.md`)
- Add HTMX dynamic behaviors (`hx-post`, `hx-target`, etc.)
- Update E2E test to assert full functionality (interactions, data persistence)

### 5. Pre-Submission
- Run `poe lint` — fix all errors
- Run `poe test` — all tests must pass
- Self-review checklist:
  - [ ] New test files created
  - [ ] `selectinload` used for relationships
  - [ ] No commented-out code or TODO placeholders

### 6. Submit
- Commit: `git commit -m "feat: <description> (#<IssueID>)"`
- Push: `git push origin HEAD`
- PR: `gh pr create --fill`

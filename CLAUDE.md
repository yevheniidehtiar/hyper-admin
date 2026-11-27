# HyperAdmin — Project Guide

For architectural principles, naming conventions, module boundaries, and dependency rules,
see [`CONSTITUTION.md`](CONSTITUTION.md). All code must comply with it. Build bottom-up:
domain models → business logic → API/views → UI.

Design documents for larger features live in `docs/specs/` (template: `docs/specs/TEMPLATE.md`);
they are developer-only and not published to the docs site.

---

# Commands

```bash
poe lint              # Run all linters (pre-commit hooks: ruff, mypy, commitizen)
poe test              # Run all tests (unit + e2e)
poe test:unit         # Unit tests only (pytest with coverage)
poe test:e2e          # E2E tests with Playwright
poe test:cov-diff     # Unit tests + 100% coverage of lines changed vs origin/develop (required before push)
poe deps:bump         # Bump deps and verify across compatibility matrix
poe docs:serve        # Serve docs locally on port 8080 (Zensical, ephemeral Python 3.13 env)
poe docs:build        # Build documentation site into site/ (zensical build --clean)
uv sync --all-extras  # Install all dependencies
uv run <cmd>          # Run commands in the virtual environment
```

Use `poe docs:build` / `poe docs:serve` for the docs site: they run Zensical in an isolated 3.13 env so the docs stack never touches the dev environment.

## Dependency Management

HyperAdmin is a library consumed by other projects, so dependency bounds matter:

- **Runtime deps** (`[project.dependencies]`): Keep conservative lower bounds (e.g., `pydantic>=2.7`). Only bump when code requires a newer API or a security fix exists.
- **Dev deps** (`[project.optional-dependencies].dev`): Bump freely to latest — they only affect contributors.
- **Dependabot**: Configured for weekly automated dev dep bumps via PR.

### Bumping Dependencies

```bash
poe deps:bump         # Bump lock file and verify across compatibility matrix
```

This command:
1. Runs `uv lock --upgrade` to resolve latest compatible versions
2. Verifies lint + unit tests + security checks across 4 combos:
   - Python 3.11 + lowest-direct
   - Python 3.14 + lowest-direct
   - Python 3.14 + highest
   - Python 3.15 + highest
3. Restores the default environment when done (even on failure)

## Branch and Commit Conventions

See [`.claude/rules/git-workflow.md`](.claude/rules/git-workflow.md) for commit message format,
commit authorship, and PR creation conventions. Code style lives in
[`.claude/rules/code-style.md`](.claude/rules/code-style.md), testing rules (TDD, 100% patch
coverage) in [`.claude/rules/testing.md`](.claude/rules/testing.md), and the Given/When/Then
scenario format for tests in [`.claude/rules/bdd-conventions.md`](.claude/rules/bdd-conventions.md).

---

# E2E Testing Conventions

## E2E Selector Convention

E2E tests use Playwright's accessibility-first locators. Query priority (highest to lowest):

1. `page.get_by_role()` — buttons, links, headings, rows
2. `page.get_by_label()` — form inputs (matched via `<label for>`)
3. `page.get_by_text()` — static content assertions
4. `page.get_by_test_id()` — elements without a natural accessible role

**Do NOT** use `page.locator('.ha-*')` or positional DOM selectors in E2E tests. `ha-*` classes are for styling only and must not appear in test selectors.

### `data-testid` reference

| Template element | `data-testid` |
|-----------------|---------------|
| Sidebar `<aside>` | `sidebar` |
| Sidebar nav link (model or plugin page) | `nav-{key}` (`NavItem.testid`, e.g. `nav-order`) |
| Sidebar nav group | `nav-group-{slug}` |
| Sidebar icon-rail toggle | `sidebar-rail-toggle` |
| Sidebar Pinned group | `nav-pinned` |
| Sidebar pin toggle (per item) | `nav-pin-{key}` (e.g. `nav-pin-order`) |
| List table | `list-table` |
| Each table row | `list-row` |
| Row link (title cell, or chevron when every column is editable) | `row-link` |
| Delete action button | `row-delete-btn` |
| Detail page Edit link | `detail-edit-link` |
| Detail page Delete button | `detail-delete-btn` |
| Edit page View link | `form-view-link` |
| Edit page Delete button | `form-delete-btn` |
| Shared delete confirm dialog | `dialog-confirm-delete` |
| Search input | `search-input` |
| List Filters button (collapses / opens the filter panel) / its active-filter badge | `filters-toggle` / `filters-toggle-count` |
| Pagination info | `pagination-info` |
| Pagination previous | `pagination-prev` |
| Pagination next | `pagination-next` |
| Pagination current page | `pagination-page` |
| Rows-per-page group / option | `page-size` / `page-size-{n}` |
| Sort link (per field) | `sort-{field_name}` |
| Command palette `<dialog>` | `command-palette` |
| Palette search input | `palette-input` |
| Palette result (each option) | `palette-result` |
| Navbar "Search… ⌘K" button | `palette-trigger` |
| Account-menu theme toggle (phones, below 640px) | `theme-toggle-menu` |
| Account-menu language select (phones, below 640px) | `locale-switcher-menu` |
| Keyboard shortcuts `<dialog>` (`?`) | `shortcuts-overlay` |
| Shortcuts overlay "Single-key shortcuts" switch | `shortcuts-toggle` |
| Create New link | `create-link` |
| Form (create/update) | `model-form` |
| Sticky form actions bar (create/update) | `form-actions` |
| Field error list | `{field_name}-errors` |
| Form error summary (lists invalid fields) | `error-summary` |
| Detail fields container | `detail-fields` |
| Report filter sidebar / its form / Apply button | `report-filters` / `report-filter-form` / `report-filter-apply` |
| Report filter Reset / Clear all links | `report-filters-reset` / `report-filters-clear` |
| Report applied-filter chips / count / ignored-filter alert | `report-applied-filters` / `report-filter-count` / `report-filter-ignored` |
| Login page OAuth provider button | `oauth-btn-{provider}` |
| Login page OAuth divider / button group | `oauth-divider` / `oauth-buttons` |
| Login page notice (session expired) | `login-notice` |
| OAuth account-exists page | `oauth-link-required` |
| OAuth settings: provider row | `oauth-identity-{provider}` |
| OAuth settings: link / unlink control | `oauth-link-{provider}` / `oauth-unlink-{provider}` |
| OAuth settings: flash / error | `oauth-settings-flash` / `oauth-settings-error` |
| Request-failure alert (5xx / network error on an HTMX request) | `request-error-toast` |
| Status pill in a list row | `row-status` |
| ERP dashboard figures grid / its live region | `dashboard-figures` / `dashboard-figures-region` |
| ERP dashboard figure tile | `figure-{name}` (e.g. `figure-overdue-invoices`) |
| Reports dashboard grid / empty state / "Reset layout" button | `dashboard-grid` / `dashboard-empty` / `dashboard-reset` |
| Reports dashboard card / its stat value | `widget-{key}` (e.g. `widget-stat-orders-revenue`) / `stat-{key}` |
| Dashboard card "Move up" / "Move down" / drag handle | `widget-move-up` / `widget-move-down` / `widget-drag-handle` |
| Dashboard card link to its report / loading skeleton | `widget-open` / `widget-loading` |
| Dashboard card error state / its Retry button / 403 fragment | `widget-error` / `widget-retry` / `widget-forbidden` |
| Dashboard quick actions list / its empty line | `widget-actions` / `widget-actions-empty` |
| Dashboard move announcement (live region) | `dashboard-live` |
| Sidebar "Dashboard" link (`dashboard_home=False`) | `nav-dashboard` |

When adding new interactive or assertable elements to templates, add a `data-testid` following the `<view>-<element>` naming pattern.

---

## Project Management: GitPM

All issue, epic, and milestone state is managed via **GitPM** (`.meta/` files).
Read and write `.meta/` directly instead of using `gh issue` or the GitHub Projects API.
PRs are still managed via `gh pr`.

```bash
./scripts/gitpm.sh validate                        # Validate .meta/ tree (run before committing .meta/)
./scripts/gitpm.sh status                          # Progress across milestones and epics
```

Never run `gitpm push` or `gitpm sync` locally. After a `.meta/` change merges to `develop`,
the **GitPM Sync** workflow (`.github/workflows/gitpm-sync.yml`) pushes it to GitHub issues and
milestones, keeping its sync state on the `gitpm-state` branch. PRs that touch `.meta/` get a
validation check and a dry-run preview. `.meta/` is the source of truth: edits made only on
GitHub are overwritten the next time that entity changes.

## Key Files

| Path | Purpose |
|------|---------|
| `CONSTITUTION.md` | Architecture, module boundaries, naming and dependency rules |
| `.meta/` | Git-native project state (stories, epics, milestones) |
| `scripts/gitpm.sh` | GitPM CLI wrapper |
| `pyproject.toml` (`[tool.poe.tasks]`) | All dev tasks (`poe <task>`) |
| `scripts/` | Automation helpers (load tests, demo media, release smoke test) |
| `.claude/commands/` | Claude slash commands (lint, test, refactor, optimize, scaffold, docs-maintain, bootstrap, release, wt) |
| `.claude/rules/` | Code style, testing, BDD scenario format, git workflow |
| `docs/` | Zensical documentation source (config: `zensical.toml`) |
| `docs/specs/` | Developer-only design documents |

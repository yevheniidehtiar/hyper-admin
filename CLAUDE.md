# Project Constitution

For architectural principles, naming conventions, module boundaries, and dependency rules,
see [`CONSTITUTION.md`](CONSTITUTION.md). All planning and code generation must comply with it.

The Software Architect agent role and its review checklist are defined in [`AGENTS.md`](AGENTS.md).

---

# Hook-First Planning Instructions

## Objective

Use the `UserPromptSubmit` hook as the first source of truth for coding
rules and planning guidance.

These instructions apply to both `AGENTS.md` and `CLAUDE.md`.

## Hook-First Rule

Before answering any request that may lead to planning, code generation,
refactoring, architecture, or tests, you MUST first use the hook-injected
context tagged `[Coding Rules from Rippletide]` when it is present.

This requirement applies especially to plan mode requests such as:

- `/plan ...`
- requests that ask for a step-by-step implementation plan
- requests that ask what should be built before writing code

## Required Behavior Before Plan Mode

When the user enters a plan-style request, the assistant must treat the
hook result as input that is processed before producing the plan.

If hook rules are present:

### E2E Selector Convention

E2E tests use Playwright's accessibility-first locators. Query priority (highest to lowest):

1. `page.get_by_role()` — buttons, links, headings, rows
2. `page.get_by_label()` — form inputs (matched via `<label for>`)
3. `page.get_by_text()` — static content assertions
4. `page.get_by_test_id()` — elements without a natural accessible role

**Do NOT** use `page.locator('.ha-*')` or positional DOM selectors in E2E tests. `ha-*` classes are for styling only and must not appear in test selectors.

#### `data-testid` reference

| Template element | `data-testid` |
|-----------------|---------------|
| Sidebar `<aside>` | `sidebar` |
| List table | `list-table` |
| Each table row | `list-row` |
| View action link | `row-view-link` |
| Edit action link | `row-edit-link` |
| Delete action button | `row-delete-btn` |
| Search input | `search-input` |
| Pagination info | `pagination-info` |
| Pagination previous | `pagination-prev` |
| Pagination next | `pagination-next` |
| Pagination current page | `pagination-page` |
| Sort link (per field) | `sort-{field_name}` |
| Create New link | `create-link` |
| Form (create/update) | `model-form` |
| Field error list | `{field_name}-errors` |
| Detail fields container | `detail-fields` |

When adding new interactive or assertable elements to templates, add a `data-testid` following the `<view>-<element>` naming pattern.
1. Begin the response by explicitly naming the rules being applied.
2. Make the plan consistent with those rules.
3. Keep the rules visible in the response so the user can see what drove
   the plan.

Use a direct format such as:

`Applying rules: Rule A, Rule B, Rule C`

If the hook returns no rules, say so explicitly before continuing:

`Applying rules: none returned by hook`

## Required Behavior Before Code Generation

Before generating code, examples, patches, refactors, or tests:

1. Read the hook-injected rules first.
2. State which rules are being applied.
3. Ensure the implementation follows those rules.
4. If relevant, explain which rule changed the implementation or plan.

## Query Source

The hook query should use the user's current request text, not a fixed
prompt. For example, if the user submits:

`/plan write a hello world`

then the hook query should contain that exact text as the request being
evaluated.

## Enforcement

Do not produce planning or code output silently.

Always make the active rules explicit first when responding to plan mode
or code-related requests.

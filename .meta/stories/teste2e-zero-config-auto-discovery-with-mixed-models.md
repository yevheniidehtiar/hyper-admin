---
type: story
id: Sp0awD_opAo9
title: "test(e2e): zero-config auto-discovery with mixed models"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 373
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e4b8c285cbc96e675469e2e61ab36419c69958e0b194f733863e86aa5ac0d356
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T09:00:03Z
updated_at: 2026-03-31T20:43:37Z
---

## Context

Playwright E2E test with 3 models (FK relationships, Enum field, various types), mounted without explicit registration. Verifies all appear with working CRUD, inferred columns, and human-readable labels.

## Scenarios

**Scenario: all auto-discovered models appear in sidebar**
  Given 3 SQLModel models: Category (name, description), Product (name, price, category_id FK, status Enum), Tag (label)
  And   no explicit `site.register()` calls
  When  the admin dashboard is loaded
  Then  the sidebar shows Category, Product, and Tag

**Scenario: inferred list_display shows key fields**
  Given Product model with fields: id, name, price, category_id, status, created_at
  When  the Product list view is loaded
  Then  the table shows id, name, price, status, created_at (not all fields)

**Scenario: inferred field labels are human-readable**
  Given Product model with `category_id` FK field
  When  the Product list view column headers are rendered
  Then  the header shows "Category" not "category_id"

**Scenario: CRUD operations work on auto-discovered model**
  Given Product is auto-discovered (not explicitly registered)
  When  a new Product is created via the form
  Then  it appears in the list view
  And   it can be viewed, edited, and deleted

## Acceptance criteria

- [ ] New file: `tests/e2e/test_zero_config.py`
- [ ] 3 test models with FK, Enum, and various field types
- [ ] Inline `# Given / # When / # Then` comments
- [ ] Accessibility-first selectors
- [ ] Tests for sidebar presence, inferred columns, labels, and full CRUD

## Files likely affected

- `tests/e2e/test_zero_config.py` (new)
- `tests/e2e/conftest.py` (zero-config fixture)

## Dependencies

Depends on: #363, #364, #365, #366, #367, #368, #369, #370, #371

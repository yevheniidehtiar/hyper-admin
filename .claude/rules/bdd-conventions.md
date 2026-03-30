# BDD (Behavior-Driven Development) Conventions

All features in HyperAdmin are specified, planned, and tested using Behavior-Driven Development.
BDD scenarios are the contract between planning, implementation, and QA.

---

## When BDD Applies

BDD scenarios are **required** for:

- Every GitHub issue of type `feat` or `test(e2e)`
- Every `fix` issue (the scenario describes the expected behavior that was broken)
- Every `perf` issue that changes observable behavior (e.g. response time thresholds, pagination limits)
- Every epic sub-issue that describes observable user behavior
- Every E2E Playwright test (`tests/e2e/`)

BDD scenarios are **optional** (but encouraged) for:

- Unit test docstrings that describe non-trivial business logic
- `refactor`, `chore`, `docs`, `ci` issues (no observable behavior change)

---

## Scenario Format

Use plain Given/When/Then — no Gherkin tooling required.

```
Scenario: <short imperative title>
  Given <initial context / system state>
  When  <user action or system event>
  Then  <observable outcome>
  And   <additional outcome, if needed>
```

### Rules

- One scenario = one testable behavior. Do not combine multiple behaviors in one scenario.
- **Given** sets up state only — no actions.
- **When** is a single action or event.
- **Then** is an observable outcome (HTTP status, UI element, DB state, redirect).
- Use `And` to extend any step, never `But` (negations belong in a separate scenario).
- Title must be imperative and unique within the issue.

---

## GitHub Issue Structure

Every `feat` or `test(e2e)` issue body MUST include a `## Scenarios` section:

```markdown
## Scenarios

**Scenario: unauthenticated access is redirected to login**
  Given the admin has `auth_backend` configured
  When  an unauthenticated request arrives at `/admin/`
  Then  the response is a 302 redirect to `/admin/login`

**Scenario: valid login grants session and redirects to dashboard**
  Given a superuser `alice` exists with password `secret`
  When  POST `/admin/login` with `username=alice&password=secret`
  Then  the session contains `user_id = alice.id`
  And   the response is a 302 redirect to `/admin/`

**Scenario: invalid credentials show error**
  Given a superuser `alice` exists with password `secret`
  When  POST `/admin/login` with `username=alice&password=wrong`
  Then  the login page is re-rendered with an error message
  And   no session is created
```

The `## Acceptance criteria` checklist is derived from the scenarios — every scenario becomes a checkbox.

---

## Mapping Scenarios to Tests

### E2E (Playwright)

Each scenario maps to **one** Playwright test function. Name the function after the scenario title:

```python
async def test_unauthenticated_access_is_redirected_to_login(page: Page, ...) -> None:
    # Given the admin has auth_backend configured
    # (fixture provides auth-enabled app)

    # When an unauthenticated request arrives at /admin/
    response = await page.goto("/admin/")

    # Then the response is a 302 redirect to /admin/login
    assert page.url.endswith("/admin/login")
```

Inline `# Given / # When / # Then` comments are mandatory in E2E tests.
They make the mapping from scenario to code explicit and reviewable.

### Unit Tests

Unit tests for business logic SHOULD include a scenario docstring:

```python
async def test_authenticate_returns_none_for_wrong_password() -> None:
    """
    Scenario: wrong password returns None
      Given a user 'alice' with password 'secret' in the DB
      When  authenticate('alice', 'wrong') is called
      Then  the result is None
    """
    ...
```

---

## Planning Agent Rules

When the Roadmap Planning Agent creates issues:

1. Before writing acceptance criteria, draft the BDD scenarios first.
2. Each scenario becomes one checkbox in `## Acceptance criteria`.
3. The scenario set must be complete: happy path + at least one failure path per feature.
4. Size estimates are derived from scenario count:
   - 1–2 scenarios → `size:S`
   - 3–5 scenarios → `size:M`
   - 6+ scenarios → `size:L` (consider splitting the epic)

---

## BDD and the TDD Loop

BDD scenarios define **what** to test. TDD defines **when**:

```
1. Write BDD scenarios (in the issue)
2. Translate to failing tests (unit + E2E)  ← TDD red
3. Implement code to make tests pass         ← TDD green
4. Refactor                                  ← TDD refactor
5. Confirm all scenarios checked off in the issue
```

The sub-task split mandated by the planning playbook maps exactly:
- Sub-task 1 (test): translate scenarios to failing tests
- Sub-task 2 (impl): make the tests pass

---

## Scenario Anti-Patterns (Do Not Write)

| Anti-pattern | Problem | Fix |
|---|---|---|
| `Scenario: test login` | Too vague — not testable | Name the specific behavior |
| `Given nothing` | No context — fragile | Always state the relevant preconditions |
| `Then everything works` | Not observable | Name the specific response, redirect, or DB state |
| `When user does many things` | Multiple actions in one step | Split into separate scenarios |
| Scenarios covering implementation details (`Then the SessionMiddleware stores...`) | Tests internals, not behavior | Test the observable outcome (`Then session contains user_id`) |

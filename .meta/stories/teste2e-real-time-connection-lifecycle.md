---
type: story
title: "test(e2e): real-time connection lifecycle (connect / navigate / refresh / restart / auth / drain)"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:realtime
  - test
estimate: null
epic_ref: null
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Context
End-to-end Playwright coverage for every lifecycle scenario in the MVP. Uses the existing `auth_base_url` fixture (alice / secret123) for the authenticated path and `demo_base_url` for the rejection path.

## Scenarios

**Scenario: both transports open after login**
  Given a logged-in admin session
  When  the dashboard loads
  Then  `window.__rt.state` reads `"connected"` within 2 s
  And   `[data-testid="realtime-status"]` has class `is-connected`

**Scenario: navigation closes prior connections cleanly**
  Given an open connection on `/admin/`
  When  the user navigates to `/admin/users/`
  Then  the previous SSE/WS pair is closed
  And   a new pair is opened on the new page
  And   the server-side `ConnectionRegistry` count returns to its baseline within 2 s

**Scenario: page refresh re-establishes connections**
  Given an open connection
  When  the user reloads the page
  Then  a fresh pair of connections is opened
  And   the previous pair is fully unregistered (no leak)

**Scenario: server restart triggers reconnect**
  Given an open connection
  When  the server is killed and restarted within 5 s
  Then  the dot transitions green → yellow → green
  And   the page is NOT reloaded

**Scenario: unauthenticated SSE is rejected with 401**
  Given no session cookie
  When  the client GETs `/admin/realtime/sse`
  Then  the response is `401`

**Scenario: unauthenticated WS is closed with 4401**
  Given no session cookie
  When  the client opens the WS
  Then  the close event has code `4401`

## Acceptance Criteria
- [ ] `tests/e2e/test_realtime_connection_lifecycle.py` (new)
- [ ] One test per scenario, named after the scenario title
- [ ] Inline `# Given / # When / # Then` comments
- [ ] Uses `get_by_test_id("realtime-status")` for assertions
- [ ] Server-restart scenario uses a dedicated subprocess fixture (not `auth_base_url`, which is session-scoped)
- [ ] All scenarios green under `poe test:e2e -k realtime_connection_lifecycle`

## Files Likely Affected
- `tests/e2e/test_realtime_connection_lifecycle.py` (new)
- `tests/e2e/conftest.py` — possibly add a function-scoped `restartable_realtime_url` fixture

## Dependencies
Blocked by: SSE, WS, status-widget stories

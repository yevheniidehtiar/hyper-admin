# SDD: Plain ASGI middleware

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | st-perf-03 |
| Milestone | v0.7.0a (scale-core) |
| Created | 2026-11-07 |
| Last updated | 2026-11-07 |

---

## Problem

Four middleware classes subclass Starlette's `BaseHTTPMiddleware`: `LocaleMiddleware` (`i18n/middleware.py`), `StartupGuardMiddleware` (`core/lifecycle.py`), `AuthenticationMiddleware` (`auth/middleware.py`) and the realtime one (`realtime/ws.py`). Each wraps every request in an extra task and stream. On the ERP load test (400 users, 9 CPUs) the app is CPU-bound at about 300 req/s, so per-request overhead matters.

## Goals

- Convert the four classes to plain ASGI (`__init__(app, ...)`, `async __call__(scope, receive, send)`).
- No behaviour change and no public API change.

## Non-Goals

- Changing what any middleware does or the order they run in.
- Converting host-application middleware.

## BDD Scenarios

```
Scenario: non-HTTP scopes pass through untouched
  Given the admin app
  When  a websocket or lifespan scope arrives
  Then  each middleware forwards it to the inner app

Scenario: an anonymous request is redirected to login
  Given auth is configured
  When  GET /admin/ without a session
  Then  the response is a 302 to /admin/login

Scenario: a streaming response is not buffered
  Given an SSE endpoint behind the middleware stack
  When  the client reads the stream
  Then  events arrive as they are sent
```

## Design

### Architecture

Each class keeps its constructor arguments and its name, so `add_middleware` calls in `core/app.py` are unchanged. `__call__` handles `http` scopes and forwards `websocket` and `lifespan` untouched. A `Request(scope, receive)` is built where the old code used the request. Redirects and 401s are sent by calling the response object with `(scope, receive, send)`. State set on `request.state` goes to `scope["state"]`, which `Request.state` reads. The session comes from `scope["session"]`, set by `AdminSessionMiddleware` earlier in the stack.

Conversion order, one commit each: locale, startup guard, authentication, realtime.

### Data Model Changes

No data model changes.

### API / Protocol Changes

No API changes.

### Configuration Changes

No configuration changes.

## Edge Cases & Error Handling

- A response started before an exception: re-raise, never send a second response.
- Client disconnect during a streaming response: propagate, as before.
- `request.state` set by a middleware must be visible to route handlers: covered by the existing auth tests.
- Background tasks attached to responses keep running (a known `BaseHTTPMiddleware` pitfall this removes).

## Migration & Backward Compatibility

Backward compatible, no migration required. Hosts that import the middleware classes keep the same names and arguments.

## Open Questions

- None.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Plain ASGI, not a shared base class | Four small classes; a base class would be the only abstraction and hides the ASGI contract | A `PureASGIMiddleware` helper |
| Keep class names and constructors | Zero edits to the `core/app.py` hotspot | New names with aliases |

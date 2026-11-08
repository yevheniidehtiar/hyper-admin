"""Rate limiting: the limiter, its middleware and the ``Admin`` wiring (#233, #234, #235)."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from starlette.testclient import TestClient

from hyperadmin.core.app import Admin
from hyperadmin.core.rate_limit import InMemoryRateLimiter, RateLimitDecision, RateLimiter
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.rate_limit import RateLimitMiddleware

if TYPE_CHECKING:
    from starlette.types import Message, Receive, Scope, Send

pytestmark = pytest.mark.anyio


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _RecordingLimiter:
    """A custom limiter: allows ``allowed`` requests, then denies; records its keys."""

    def __init__(self, allowed: int, retry_after: int = 7) -> None:
        self.allowed = allowed
        self.retry_after = retry_after
        self.keys: list[str] = []

    async def acquire(self, key: str) -> RateLimitDecision:
        self.keys.append(key)
        if len(self.keys) <= self.allowed:
            return RateLimitDecision(allowed=True)
        return RateLimitDecision(allowed=False, retry_after=self.retry_after)


class _Downstream:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.calls += 1
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})


async def _call(
    middleware: RateLimitMiddleware,
    path: str,
    *,
    method: str = "GET",
    client: tuple[str, int] | None = ("10.0.0.1", 5000),
    scope_type: str = "http",
) -> list[Message]:
    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": scope_type,
        "method": method,
        "path": path,
        "root_path": "",
        "headers": [],
        "client": client,
    }
    await middleware(scope, receive, send)
    return sent


def _status(messages: list[Message]) -> int:
    return messages[0]["status"]


# ── InMemoryRateLimiter ────────────────────────────────────────────────────


async def test_limiter_allows_the_limit_then_denies_with_retry_after() -> None:
    """Scenario: a client over its limit is denied and told when to retry.

    Given a limit of 3 requests per 60 seconds
    When one client makes 4 requests at the same instant
    Then the first 3 are allowed and the 4th is denied with a 20 second retry
    """
    limiter = InMemoryRateLimiter(3, 60, clock=_Clock())

    decisions = [await limiter.acquire("1.1.1.1") for _ in range(4)]

    assert [d.allowed for d in decisions] == [True, True, True, False]
    assert decisions[0].retry_after == 0
    assert decisions[3].retry_after == 20


async def test_limiter_refills_over_the_window() -> None:
    """Scenario: tokens come back evenly, so a denied client is allowed after waiting."""
    clock = _Clock()
    limiter = InMemoryRateLimiter(3, 60, clock=clock)
    for _ in range(3):
        await limiter.acquire("k")
    assert not (await limiter.acquire("k")).allowed

    clock.now += 19
    assert not (await limiter.acquire("k")).allowed
    clock.now += 1.5
    assert (await limiter.acquire("k")).allowed


async def test_limiter_caps_the_refill_at_the_limit() -> None:
    """Scenario: waiting longer than a window never banks more than the limit."""
    clock = _Clock()
    limiter = InMemoryRateLimiter(2, 60, clock=clock)
    await limiter.acquire("k")
    clock.now += 10_000

    decisions = [await limiter.acquire("k") for _ in range(3)]

    assert [d.allowed for d in decisions] == [True, True, False]


async def test_limiter_counts_each_key_separately() -> None:
    """Scenario: one client's traffic does not use up another's allowance."""
    limiter = InMemoryRateLimiter(1, 60, clock=_Clock())

    assert (await limiter.acquire("a")).allowed
    assert not (await limiter.acquire("a")).allowed
    assert (await limiter.acquire("b")).allowed


async def test_limiter_bounds_the_number_of_keys() -> None:
    """Scenario: the least recently seen key is forgotten once max_keys is exceeded."""
    limiter = InMemoryRateLimiter(1, 60, max_keys=2, clock=_Clock())
    await limiter.acquire("a")
    await limiter.acquire("b")
    await limiter.acquire("c")  # evicts "a"

    assert (await limiter.acquire("a")).allowed  # a fresh bucket again
    assert not (await limiter.acquire("c")).allowed  # still remembered


@pytest.mark.parametrize(
    ("kwargs", "name"),
    [
        ({"requests_per_window": 0}, "requests_per_window"),
        ({"requests_per_window": 1, "window_seconds": 0}, "window_seconds"),
        ({"requests_per_window": 1, "max_keys": 0}, "max_keys"),
    ],
)
def test_limiter_rejects_non_positive_arguments(kwargs: dict[str, int], name: str) -> None:
    """Scenario: a limit that could never allow a request is rejected at construction."""
    with pytest.raises(ValueError, match=name):
        InMemoryRateLimiter(**kwargs)


def test_limiters_satisfy_the_protocol() -> None:
    """Scenario: the built-in and a custom limiter are both RateLimiter implementations."""
    assert isinstance(InMemoryRateLimiter(1), RateLimiter)
    assert isinstance(_RecordingLimiter(1), RateLimiter)


# ── RateLimitMiddleware ────────────────────────────────────────────────────


async def test_middleware_answers_429_with_retry_after() -> None:
    """Scenario: requests over the per-client limit get 429 and never reach the app.

    Given a limiter that allows one request
    When the same client makes two requests
    Then the second is answered 429 with Retry-After and the app is not called
    """
    downstream = _Downstream()
    limiter = _RecordingLimiter(allowed=1, retry_after=7)
    middleware = RateLimitMiddleware(downstream, limiter=limiter)

    first = await _call(middleware, "/anything")
    second = await _call(middleware, "/anything")

    assert _status(first) == 204
    assert _status(second) == 429
    assert dict(second[0]["headers"])[b"retry-after"] == b"7"
    assert b"Too many requests" in second[1]["body"]
    assert downstream.calls == 1


async def test_middleware_keys_requests_by_client_address() -> None:
    """Scenario: the limit is per client address; a missing client counts as 'unknown'."""
    limiter = _RecordingLimiter(allowed=10)
    middleware = RateLimitMiddleware(_Downstream(), limiter=limiter)

    await _call(middleware, "/x", client=("203.0.113.9", 1))
    await _call(middleware, "/x", client=None)

    assert limiter.keys == ["203.0.113.9", "unknown"]


async def test_middleware_skips_static_assets() -> None:
    """Scenario: static assets are neither counted nor limited."""
    downstream = _Downstream()
    limiter = _RecordingLimiter(allowed=0)
    middleware = RateLimitMiddleware(downstream, limiter=limiter)

    messages = await _call(middleware, "/static/css/app.css")

    assert _status(messages) == 204
    assert limiter.keys == []


async def test_middleware_ignores_non_http_scopes() -> None:
    """Scenario: websocket and lifespan scopes pass through unlimited."""
    downstream = _Downstream()
    limiter = _RecordingLimiter(allowed=0)
    middleware = RateLimitMiddleware(downstream, limiter=limiter)

    await _call(middleware, "/ws", scope_type="websocket")

    assert downstream.calls == 1
    assert limiter.keys == []


async def test_middleware_only_limits_below_the_admin_prefix() -> None:
    """Scenario: host routes, even ones that share the prefix text, are left alone."""
    limiter = _RecordingLimiter(allowed=0)
    middleware = RateLimitMiddleware(_Downstream(), limiter=limiter, admin_prefix="/admin")

    assert _status(await _call(middleware, "/api/items")) == 204
    assert _status(await _call(middleware, "/administrator")) == 204
    assert _status(await _call(middleware, "/admin/orders")) == 429
    assert _status(await _call(middleware, "/admin")) == 429
    assert _status(await _call(middleware, "/admin/static/app.js")) == 204
    assert len(limiter.keys) == 2


async def test_login_limiter_only_counts_login_posts() -> None:
    """Scenario: the stricter login limit applies to submitting the form, not viewing it.

    Given a login limit of one and no general limit
    When a client views the form, posts it, then posts it again
    Then viewing and the first post pass and the second post gets 429
    """
    login = _RecordingLimiter(allowed=1)
    middleware = RateLimitMiddleware(_Downstream(), login_limiter=login)

    assert _status(await _call(middleware, "/login")) == 204
    assert _status(await _call(middleware, "/login", method="POST")) == 204
    assert _status(await _call(middleware, "/login/", method="POST")) == 429
    assert _status(await _call(middleware, "/orders", method="POST")) == 204
    assert login.keys == ["10.0.0.1", "10.0.0.1"]


async def test_login_denial_does_not_use_the_general_allowance() -> None:
    """Scenario: both limits apply to a login post; either one can deny it."""
    general = _RecordingLimiter(allowed=1)
    login = _RecordingLimiter(allowed=0)
    middleware = RateLimitMiddleware(_Downstream(), limiter=general, login_limiter=login)

    assert _status(await _call(middleware, "/login", method="POST")) == 429
    assert general.keys == []

    login.allowed = 10
    assert _status(await _call(middleware, "/login", method="POST")) == 204
    assert _status(await _call(middleware, "/login", method="POST")) == 429
    assert len(general.keys) == 2


def test_middleware_needs_a_limiter() -> None:
    """Scenario: a middleware with nothing to enforce is a configuration error."""
    with pytest.raises(ValueError, match="limiter"):
        RateLimitMiddleware(_Downstream())


# ── Admin wiring ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(site._registry)
    yield
    site._registry = saved


def _client(
    *, rate_limiter: RateLimiter | None = None, router_mode: bool = False, **settings: Any
) -> TestClient:
    app = FastAPI()
    admin_settings = HyperAdminSettings(
        **settings, **({"mount_mode": "router"} if router_mode else {})
    )
    admin = Admin(app, settings=admin_settings, rate_limiter=rate_limiter)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        admin.mount("/admin")
    return TestClient(app)


def test_admin_applies_the_configured_limit() -> None:
    """Scenario: HYPERADMIN_RATE_LIMIT_REQUESTS limits admin requests per client.

    Given rate_limit_requests=2
    When a client makes three admin requests
    Then the third is answered 429 with a Retry-After header
    """
    client = _client(rate_limit_requests=2, rate_limit_window_seconds=60)

    codes = [client.get("/admin/no-such-page").status_code for _ in range(3)]

    assert codes == [404, 404, 429]
    assert int(client.get("/admin/no-such-page").headers["retry-after"]) >= 1


def test_admin_limits_nothing_by_default() -> None:
    """Scenario: without a limit configured, no request is ever throttled."""
    client = _client()

    assert {client.get("/admin/no-such-page").status_code for _ in range(20)} == {404}


def test_admin_leaves_host_routes_and_static_assets_unlimited() -> None:
    """Scenario: the limit covers admin pages only."""
    app = FastAPI()

    @app.get("/ping")
    def ping() -> str:
        return "pong"

    Admin(app, settings=HyperAdminSettings(rate_limit_requests=1)).mount("/admin")
    client = TestClient(app)

    assert client.get("/admin/no-such-page").status_code == 404
    assert client.get("/admin/no-such-page").status_code == 429
    assert {client.get("/ping").status_code for _ in range(5)} == {200}
    assert {client.get("/admin/static/missing.css").status_code for _ in range(5)} == {404}


def test_admin_prefers_an_explicit_limiter_over_settings() -> None:
    """Scenario: Admin(rate_limiter=...) replaces the in-memory limiter from settings."""
    limiter = _RecordingLimiter(allowed=1, retry_after=42)
    client = _client(rate_limiter=limiter, rate_limit_requests=1000)

    first = client.get("/admin/no-such-page")
    second = client.get("/admin/no-such-page")

    assert first.status_code == 404
    assert second.status_code == 429
    assert second.headers["retry-after"] == "42"


def test_admin_limits_login_posts_separately() -> None:
    """Scenario: rate_limit_login_requests throttles the login form on its own."""
    client = _client(rate_limit_login_requests=1)

    assert client.post("/admin/login").status_code != 429
    assert client.post("/admin/login").status_code == 429
    assert {client.get("/admin/no-such-page").status_code for _ in range(5)} == {404}


def test_admin_router_mode_limits_only_below_the_prefix() -> None:
    """Scenario: in the legacy router mode the middleware sits on the host app."""
    client = _client(router_mode=True, rate_limit_requests=1)

    assert client.get("/admin/no-such-page").status_code == 404
    assert client.get("/admin/no-such-page").status_code == 429
    assert client.get("/elsewhere").status_code == 404


@pytest.mark.parametrize(
    "field", ["rate_limit_requests", "rate_limit_login_requests", "rate_limit_window_seconds"]
)
def test_settings_reject_a_non_positive_limit(field: str) -> None:
    """Scenario: a limit or window below one is rejected at startup."""
    with pytest.raises(ValidationError):
        HyperAdminSettings(**{field: 0})


def test_settings_read_the_limit_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: HYPERADMIN_RATE_LIMIT_* configure the limit without code."""
    monkeypatch.setenv("HYPERADMIN_RATE_LIMIT_REQUESTS", "100")
    monkeypatch.setenv("HYPERADMIN_RATE_LIMIT_WINDOW_SECONDS", "10")

    settings = HyperAdminSettings()

    assert (settings.rate_limit_requests, settings.rate_limit_window_seconds) == (100, 10)

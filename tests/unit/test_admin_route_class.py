"""``HyperAdminRoute``: auth-error translation, token-cookie bridge and CSRF hook.

st-v058-byoa-38, SDD B.2 (and B.4 for the token cookie). The route class is
exercised through FastAPI's own machinery: an admin sub-app mounted at
``/admin`` whose router is included with the bridge dependency, exactly as
``Admin(auth=ExternalAuth(...))`` will wire it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse, PlainTextResponse, Response

from hyperadmin.auth.bridge import ExternalAuth, build_admin_dependency
from hyperadmin.core.auth import AdminAccessDenied
from hyperadmin.views.route import make_admin_route_class
from hyperadmin.views.urls import AdminScopeMiddleware

_oauth2 = OAuth2PasswordBearer(tokenUrl="token", auto_error=True)


class _HostUser:
    def __init__(self, name: str, *, is_staff: bool = True) -> None:
        self.id = name
        self.username = name
        self.is_staff = is_staff


#: Tokens the fake host accepts; anything else is a host 401.
_TOKENS = {"token-a": _HostUser("A"), "token-b": _HostUser("B")}


def bearer_user(token: str = Depends(_oauth2)) -> _HostUser:
    """A host ``get_user`` built on ``OAuth2PasswordBearer(auto_error=True)``."""
    user = _TOKENS.get(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def anonymous_user() -> None:
    return None


def staff_user() -> _HostUser:
    return _HostUser("staff")


def _admin_router(route_class: type[Any]) -> APIRouter:
    router = APIRouter(route_class=route_class)

    @router.get("/")
    async def dashboard(request: Request) -> dict[str, Any]:
        return {"user": request.state.user.username}

    @router.get("/order")
    async def order_list() -> dict[str, str]:
        return {"ok": "list"}

    @router.delete("/order/{item_id}")
    async def order_delete(item_id: int) -> dict[str, int]:
        return {"deleted": item_id}

    @router.get("/realtime/sse")
    async def sse() -> dict[str, str]:
        return {"ok": "sse"}

    @router.get("/forbidden-view")
    async def forbidden_view() -> None:
        raise HTTPException(status_code=403, detail="No change permission")

    @router.get("/missing")
    async def missing() -> None:
        raise HTTPException(status_code=404, detail="Nope")

    @router.get("/denied-in-view")
    async def denied_in_view() -> None:
        raise AdminAccessDenied

    return router


def _client(
    get_user: Callable[..., Any],
    *,
    can_access: Callable[[Any], bool] | None = None,
    route_kwargs: dict[str, Any] | None = None,
    router: APIRouter | None = None,
) -> TestClient:
    auth_kwargs: dict[str, Any] = {"get_user": get_user}
    if can_access is not None:
        auth_kwargs["can_access"] = can_access
    auth = ExternalAuth(**auth_kwargs)
    route_class = make_admin_route_class(**(route_kwargs or {}))
    sub_app = FastAPI()
    sub_app.include_router(
        router or _admin_router(route_class),
        dependencies=[Depends(build_admin_dependency(auth))],
    )
    host = FastAPI()
    host.mount("/admin", sub_app)
    return TestClient(host, follow_redirects=False)


_LOGIN = {"login_url": "/login"}
_COOKIE = {"login_url": "/login", "token_cookie": "hyperadmin_token"}


# --- Scenarios ---------------------------------------------------------------


def test_anonymous_browser_redirected() -> None:
    """
    Scenario: anonymous browser redirected
      Given ExternalAuth(login_url='/login')
      And   dep returns None
      When  GET /admin/order?page=2 is requested
      Then  the response is 303 to /login?next=%2Fadmin%2Forder%3Fpage%3D2
    """
    client = _client(anonymous_user, route_kwargs=_LOGIN)

    response = client.get("/admin/order?page=2")

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fadmin%2Forder%3Fpage%3D2"


def test_host_401_treated_as_anonymous() -> None:
    """
    Scenario: host 401 treated as anonymous
      Given dep uses OAuth2PasswordBearer(auto_error=True)
      When  GET /admin/ is requested without Authorization
      Then  the response is 303 to login_url
    """
    client = _client(bearer_user, route_kwargs=_LOGIN)

    response = client.get("/admin/")

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fadmin%2F"


def test_htmx_gets_hx_redirect() -> None:
    """
    Scenario: HTMX gets HX-Redirect
      Given dep returns None
      When  an HX-Request DELETE /admin/order/5 is sent
      Then  the response is 401 with HX-Redirect
    """
    client = _client(anonymous_user, route_kwargs=_LOGIN)

    response = client.delete("/admin/order/5", headers={"HX-Request": "true"})

    assert response.status_code == 401
    assert response.headers["hx-redirect"] == "/login?next=%2Fadmin%2Forder%2F5"
    assert "location" not in response.headers


def test_can_access_failure_is_403() -> None:
    """
    Scenario: can_access failure is 403
      Given can_access returns False
      When  GET /admin/ is requested
      Then  the response is 403 without redirect
    """
    client = _client(staff_user, can_access=lambda _user: False, route_kwargs=_LOGIN)

    response = client.get("/admin/", headers={"Accept": "text/html"})

    assert response.status_code == 403
    assert "location" not in response.headers
    assert "can_access" in response.text


def test_header_wins_over_cookie() -> None:
    """
    Scenario: header wins over cookie
      Given a token cookie for A
      When  GET /admin/ is sent with Authorization for B
      Then  request.state.user is B
    """
    client = _client(bearer_user, route_kwargs=_COOKIE)
    client.cookies.set("hyperadmin_token", "token-a")

    response = client.get("/admin/", headers={"Authorization": "Bearer token-b"})

    assert response.status_code == 200
    assert response.json() == {"user": "B"}


def test_api_prefix_gets_401() -> None:
    """
    Scenario: API prefix gets 401
      Given dep returns None
      When  GET /admin/realtime/sse is requested
      Then  the response is 401
    """
    client = _client(anonymous_user, route_kwargs=_LOGIN)

    response = client.get("/admin/realtime/sse")

    assert response.status_code == 401
    assert "location" not in response.headers
    assert "hx-redirect" not in response.headers


# --- Token-cookie bridge ------------------------------------------------------


def test_token_cookie_is_bridged_into_authorization() -> None:
    """
    Scenario: cookie alone authenticates
      Given a token cookie for A and no Authorization header
      When  GET /admin/ is requested
      Then  request.state.user is A
    """
    client = _client(bearer_user, route_kwargs=_COOKIE)
    client.cookies.set("hyperadmin_token", "token-a")

    response = client.get("/admin/")

    assert response.status_code == 200
    assert response.json() == {"user": "A"}


def test_token_cookie_uses_configured_scheme() -> None:
    """
    Scenario: the bridged header carries the configured scheme
      Given TokenCookie(scheme='Token') and a token cookie 'abc'
      When  GET /admin/ is requested
      Then  the handler sees Authorization: Token abc
    """
    route_class = make_admin_route_class(token_cookie="tk", token_scheme="Token")
    router = APIRouter(route_class=route_class)

    @router.get("/")
    async def show(request: Request) -> dict[str, str | None]:
        return {"authorization": request.headers.get("authorization")}

    client = _client(staff_user, router=router)
    client.cookies.set("tk", "abc")

    assert client.get("/admin/").json() == {"authorization": "Token abc"}


def test_empty_or_unconfigured_token_cookie_is_not_bridged() -> None:
    """
    Scenario: nothing to bridge
      Given an empty token cookie, or a cookie the admin was not told about
      When  GET /admin/ is requested
      Then  no Authorization header is added
    """
    route_class = make_admin_route_class(token_cookie="tk")
    router = APIRouter(route_class=route_class)

    @router.get("/")
    async def show(request: Request) -> dict[str, str | None]:
        return {"authorization": request.headers.get("authorization")}

    client = _client(staff_user, router=router)
    client.cookies.set("tk", "")
    assert client.get("/admin/").json() == {"authorization": None}

    unconfigured = _client(staff_user, router=_show_auth_router(make_admin_route_class()))
    unconfigured.cookies.set("hyperadmin_token", "token-a")
    assert unconfigured.get("/admin/").json() == {"authorization": None}


def _show_auth_router(route_class: type[Any]) -> APIRouter:
    router = APIRouter(route_class=route_class)

    @router.get("/")
    async def show(request: Request) -> dict[str, str | None]:
        return {"authorization": request.headers.get("authorization")}

    return router


def test_rejected_cookie_token_is_cleared_before_redirect() -> None:
    """
    Scenario: a dead cookie never causes a login loop
      Given a token cookie the host rejects with 401
      When  GET /admin/order is requested
      Then  the response is 303 to login_url
      And   the token cookie is deleted on the admin path
    """
    client = _client(bearer_user, route_kwargs=_COOKIE)
    client.cookies.set("hyperadmin_token", "expired")

    response = client.get("/admin/order")

    assert response.status_code == 303
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith('hyperadmin_token="";')
    assert "Max-Age=0" in set_cookie
    assert "Path=/admin" in set_cookie


def test_header_token_rejection_keeps_the_cookie() -> None:
    """
    Scenario: a rejected header token leaves the cookie alone
      Given no token cookie
      When  GET /admin/order is sent with a bad Authorization header
      Then  the response is 303 to login_url
      And   no cookie is set or cleared
    """
    client = _client(bearer_user, route_kwargs=_COOKIE)

    response = client.get("/admin/order", headers={"Authorization": "Bearer bad"})

    assert response.status_code == 303
    assert "set-cookie" not in response.headers


# --- Auth-error table (SDD B.2) ----------------------------------------------


def test_login_url_with_query_appends_next() -> None:
    """
    Scenario: login_url that already has a query string
      Given ExternalAuth(login_url='/login?app=admin', next_param='return_to')
      When  an anonymous GET /admin/order is requested
      Then  next is appended with '&' under the configured parameter name
    """
    client = _client(
        anonymous_user,
        route_kwargs={"login_url": "/login?app=admin", "next_param": "return_to"},
    )

    response = client.get("/admin/order")

    assert response.headers["location"] == "/login?app=admin&return_to=%2Fadmin%2Forder"


def test_without_login_url_browser_gets_sign_in_page() -> None:
    """
    Scenario: no login_url, plain browser
      Given ExternalAuth without login_url
      And   dep returns None
      When  GET /admin/order is requested
      Then  the response is a 401 HTML page asking to sign in to the host application
    """
    client = _client(anonymous_user)

    response = client.get("/admin/order")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("text/html")
    assert "Sign in to the host application" in response.text


def test_without_login_url_htmx_gets_hx_refresh() -> None:
    """
    Scenario: no login_url, HTMX
      Given ExternalAuth without login_url
      And   dep returns None
      When  an HX-Request GET /admin/order is sent
      Then  the response is 401 with HX-Refresh: true
    """
    client = _client(anonymous_user)

    response = client.get("/admin/order", headers={"HX-Request": "true"})

    assert response.status_code == 401
    assert response.headers["hx-refresh"] == "true"


def test_access_denied_htmx_and_api_are_bare_403() -> None:
    """
    Scenario: can_access failure for HTMX and API callers
      Given can_access returns False
      When  an HX-Request GET /admin/ and a GET /admin/realtime/sse are sent
      Then  both responses are 403 without the HTML page
    """
    client = _client(staff_user, can_access=lambda _user: False)

    htmx = client.get("/admin/", headers={"HX-Request": "true"})
    api = client.get("/admin/realtime/sse", headers={"Accept": "text/html"})

    assert htmx.status_code == 403
    assert "can_access" not in htmx.text
    assert api.status_code == 403
    assert "can_access" not in api.text


def test_host_403_during_dependency_solving_is_access_denied() -> None:
    """
    Scenario: host get_user chain raises 403
      Given the host dependency raises HTTPException(403)
      When  GET /admin/ is requested
      Then  the response is the 403 can_access page
    """

    def get_user() -> None:
        raise HTTPException(status_code=403, detail="Inactive account")

    client = _client(get_user)

    response = client.get("/admin/", headers={"Accept": "text/html"})

    assert response.status_code == 403
    assert "can_access" in response.text


def test_view_403_passes_through_unchanged() -> None:
    """
    Scenario: a view's permission 403 is not the can_access page
      Given an authenticated admin user
      When  a view raises HTTPException(403)
      Then  FastAPI's own 403 response comes back unchanged
    """
    client = _client(staff_user)

    response = client.get("/admin/forbidden-view", headers={"Accept": "text/html"})

    assert response.status_code == 403
    assert response.json() == {"detail": "No change permission"}


def test_admin_access_denied_from_view_is_access_denied() -> None:
    """
    Scenario: AdminAccessDenied is the can_access page in any phase
      Given an authenticated admin user
      When  a view raises AdminAccessDenied
      Then  the response is the 403 can_access page
    """
    client = _client(staff_user)

    response = client.get("/admin/denied-in-view")

    assert response.status_code == 403
    assert "can_access" in response.text


def test_other_errors_pass_through() -> None:
    """
    Scenario: any other error is not translated
      Given an authenticated admin user, and a host dep raising 400
      When  a view raises HTTPException(404), and the 400 dep runs
      Then  both responses are FastAPI's own, unchanged
    """
    client = _client(staff_user)
    assert client.get("/admin/missing").json() == {"detail": "Nope"}

    def bad_request() -> None:
        raise HTTPException(status_code=400, detail="Bad header")

    bad = _client(bad_request, route_kwargs=_LOGIN)
    response = bad.get("/admin/order")
    assert response.status_code == 400
    assert response.json() == {"detail": "Bad header"}


def test_view_401_is_not_a_login_redirect() -> None:
    """
    Scenario: a 401 raised by a view (not the host dependency) passes through
      Given an authenticated admin user
      When  a view raises HTTPException(401)
      Then  the response is FastAPI's own 401, not a redirect
    """
    route_class = make_admin_route_class(login_url="/login")
    router = APIRouter(route_class=route_class)

    @router.get("/")
    async def view() -> None:
        raise HTTPException(status_code=401, detail="Upstream said no")

    client = _client(staff_user, router=router)

    response = client.get("/admin/")

    assert response.status_code == 401
    assert response.json() == {"detail": "Upstream said no"}


def test_router_mode_next_and_api_prefix_use_the_admin_path() -> None:
    """
    Scenario: legacy router mode uses the full admin path
      Given the admin router is included at /admin on a host with AdminScopeMiddleware
      When  anonymous GET /admin/order?x=1 and GET /admin/realtime/sse are requested
      Then  next is the full admin path, and the realtime path is an API 401
    """
    auth = ExternalAuth(get_user=anonymous_user)
    host = FastAPI()
    host.include_router(
        _admin_router(make_admin_route_class(login_url="/login")),
        prefix="/admin",
        dependencies=[Depends(build_admin_dependency(auth))],
    )
    host.add_middleware(AdminScopeMiddleware, namespace=None, prefix="/admin")
    client = TestClient(host, follow_redirects=False)

    page = client.get("/admin/order?x=1")
    api = client.get("/admin/realtime/sse")

    assert page.status_code == 303
    assert page.headers["location"] == "/login?next=%2Fadmin%2Forder%3Fx%3D1"
    assert api.status_code == 401


# --- CSRF hook (pipeline order, SDD B.2 steps 1-4) ----------------------------


class _RecordingCsrf:
    """A CSRF hook that records what it saw and can be told to reject."""

    def __init__(self, *, reject: bool = False, read_form: bool = False) -> None:
        self.reject = reject
        self.read_form = read_form
        self.verified: list[Request] = []
        self.form_token: Any = None
        self.attached: list[tuple[Request, Response]] = []

    async def verify(self, request: Request) -> Response | None:
        self.verified.append(request)
        if self.read_form:
            form = await request.form()
            self.form_token = form.get("csrf_token")
        if self.reject:
            return PlainTextResponse(
                "CSRF token missing or invalid",
                status_code=403,
                headers={"X-HyperAdmin-CSRF": "failed"},
            )
        return None

    def attach(self, request: Request, response: Response) -> None:
        self.attached.append((request, response))
        response.headers["X-Csrf-Attached"] = "yes"


def test_csrf_failure_response_is_returned_and_handler_skipped() -> None:
    """
    Scenario: CSRF rejection short-circuits the handler
      Given an authenticated admin user and a CSRF hook that rejects
      When  DELETE /admin/order/5 is sent
      Then  the hook's 403 comes back and the handler never runs
    """
    calls: list[int] = []
    csrf = _RecordingCsrf(reject=True)
    router = APIRouter(route_class=make_admin_route_class(csrf=csrf))

    @router.delete("/order/{item_id}")
    async def order_delete(item_id: int) -> None:
        calls.append(item_id)

    client = _client(staff_user, router=router)

    response = client.delete("/admin/order/5")

    assert response.status_code == 403
    assert response.headers["x-hyperadmin-csrf"] == "failed"
    assert calls == []
    assert csrf.attached == []


def test_auth_is_solved_before_csrf() -> None:
    """
    Scenario: an anonymous POST gets the auth response, not a CSRF 403
      Given dep returns None and a CSRF hook that rejects
      When  POST /admin/order is sent
      Then  the response is 303 to login_url
      And   the CSRF hook never ran
    """
    csrf = _RecordingCsrf(reject=True)
    router = APIRouter(route_class=make_admin_route_class(login_url="/login", csrf=csrf))

    @router.post("/order")
    async def order_create() -> None:
        raise AssertionError

    client = _client(anonymous_user, router=router)

    response = client.post("/admin/order")

    assert response.status_code == 303
    assert csrf.verified == []


def test_csrf_cookie_is_attached_to_the_handler_response() -> None:
    """
    Scenario: the CSRF hook sees the handler's response on the same request
      Given an authenticated admin user and a CSRF hook that accepts
      When  GET /admin/ is requested
      Then  the hook verified and attached on the request the handler received
    """
    csrf = _RecordingCsrf()
    seen: list[Request] = []
    router = APIRouter(route_class=make_admin_route_class(csrf=csrf))

    @router.get("/")
    async def dashboard(request: Request) -> JSONResponse:
        seen.append(request)
        return JSONResponse({"ok": True})

    client = _client(staff_user, router=router)

    response = client.get("/admin/")

    assert response.status_code == 200
    assert response.headers["x-csrf-attached"] == "yes"
    assert csrf.verified[0] is seen[0]
    assert csrf.attached[0][0] is seen[0]


def test_multipart_post_with_cookie_token_and_body_csrf_reaches_handler_intact() -> None:
    """
    Scenario: plain multipart POST with the token cookie and a body csrf_token
      Given a token cookie for A and a CSRF hook that reads the form
      When  a multipart POST with csrf_token, a text field and a file is sent
      Then  the hook read the csrf_token from the body
      And   the handler receives every field, the file intact
    """
    csrf = _RecordingCsrf(read_form=True)
    router = APIRouter(
        route_class=make_admin_route_class(token_cookie="hyperadmin_token", csrf=csrf)
    )

    @router.post("/order")
    async def order_create(request: Request) -> dict[str, Any]:
        form = await request.form()
        upload = form["attachment"]
        content = await upload.read()  # type: ignore[union-attr]
        return {
            "user": request.state.user.username,
            "fields": sorted(form.keys()),
            "name": form["name"],
            "csrf_token": form["csrf_token"],
            "file": content.decode(),
        }

    client = _client(bearer_user, router=router)
    client.cookies.set("hyperadmin_token", "token-a")

    response = client.post(
        "/admin/order",
        data={"csrf_token": "tok-123", "name": "Widget"},
        files={"attachment": ("a.txt", b"hello file", "text/plain")},
    )

    assert response.status_code == 200
    assert csrf.form_token == "tok-123"
    assert response.json() == {
        "user": "A",
        "fields": ["attachment", "csrf_token", "name"],
        "name": "Widget",
        "csrf_token": "tok-123",
        "file": "hello file",
    }


# --- Route class mechanics ----------------------------------------------------


def test_re_created_route_keeps_a_single_trailing_phase_marker() -> None:
    """
    Scenario: include_router re-creating a route does not duplicate the marker
      Given a HyperAdminRoute built with its own dependencies
      When  it is rebuilt from those dependencies plus a router-level one
      Then  the phase marker appears once, as the last dependency
    """
    route_class = make_admin_route_class()

    async def endpoint() -> None:
        return None

    def extra() -> None:
        return None

    first = route_class("/x", endpoint)
    rebuilt = route_class("/x", endpoint, dependencies=[Depends(extra), *first.dependencies])

    marker = first.dependencies[-1].dependency
    assert route_class.__name__ == "HyperAdminRoute"
    assert [d.dependency for d in rebuilt.dependencies] == [extra, marker]

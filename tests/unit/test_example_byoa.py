"""Boot and docs tests for ``examples/byoa`` and the existing-app guide (st-v058-byoa-51).

``examples/byoa`` is a host FastAPI app that already has its own lifespan, its
own ``/static`` mount, its own ``session`` cookie and a JWT-protected ``/api``,
with HyperAdmin added through ``Admin(auth=ExternalAuth(...), session_factory=...)``.

The example registers its models on the global ``site`` registry when it is
imported, so the ``byoa`` fixture imports it lazily and restores the registry
afterwards: no other test module sees the example's models.
"""

from __future__ import annotations

import ast
import base64
import json
import logging
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hyperadmin.core.registry import site

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "guides" / "existing-app.md"
AUTH_GUIDE = ROOT / "docs" / "guides" / "external-auth.md"
CHANGELOG = ROOT / "CHANGELOG.md"
TENANCY_SDD = ROOT / "docs" / "specs" / "multi-tenancy.md"
NAV = ROOT / "zensical.toml"

#: Marker that opens the guide's minimal wiring snippet (the "fewer than 20 lines" claim).
WIRING_MARKER = "<!-- minimal-wiring -->"
MAX_WIRING_LINES = 20


#: The admin key the tests run the example with (the example refuses the default key).
TEST_ADMIN_SECRET = "byoa-unit-test-admin-secret"


@pytest.fixture(scope="module")
def byoa() -> Iterator[Any]:
    """Import ``examples.byoa.main`` once, then restore the global ``site`` registry."""
    saved = dict(site._registry)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HYPERADMIN_SECRET_KEY", TEST_ADMIN_SECRET)
        from examples.byoa import main

        try:
            yield main
        finally:
            site._registry = saved


@pytest.fixture
def client(byoa: Any) -> Iterator[TestClient]:
    """A ``TestClient`` that runs the host lifespan (tables, seed data, ``admin.lifespan()``)."""
    with TestClient(byoa.app) as test_client:
        yield test_client


def _bearer(
    client: TestClient,
    username: str = "ada",
    password: str = "lovelace",  # noqa: S107 - the example's demo credentials
) -> str:
    """Log in through the host's own ``/token`` endpoint and return the JWT."""
    response = client.post("/token", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _session_payload(signed: str) -> dict[str, Any]:
    """Decode the JSON payload of a signed Starlette session cookie value."""
    data = signed.strip('"').split(".", 1)[0]
    return json.loads(base64.b64decode(data + "=" * (-len(data) % 4)))


def _set_cookies(response: Any) -> list[str]:
    return [v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"]


# ── Scenario: BYOA example boots ────────────────────────────────────────────


def test_byoa_example_boots(client: TestClient) -> None:
    """
    Scenario: BYOA example boots
      Given examples/byoa with its own lifespan, /static and session cookie
      When  GET /admin/ with a valid bearer and GET /health are requested
      Then  both return 200
      And   the host session cookie is untouched
    """
    # Given examples/byoa with its own lifespan, /static and session cookie
    home = client.get("/")
    assert home.status_code == 200
    host_session = client.cookies.get("session")
    assert host_session
    token = _bearer(client)

    # When GET /admin/ with a valid bearer and GET /health are requested
    dashboard = client.get("/admin/", headers=_auth(token))
    health = client.get("/health")

    # Then both return 200
    assert dashboard.status_code == 200
    assert health.status_code == 200
    # And the host session cookie is untouched
    # Compare payloads, not raw values: older Starlette re-sends (and re-signs) a
    # non-empty host session cookie on every response, so the signed value can
    # change while the host data stays the same.
    for cookie in _set_cookies(dashboard):
        if cookie.startswith("session="):
            assert _session_payload(cookie.split(";", 1)[0].split("=", 1)[1]) == {"visits": 1}
    assert _session_payload(client.cookies.get("session") or "") == {"visits": 1}
    assert _session_payload(host_session) == {"visits": 1}
    assert client.get("/").json()["visits"] == 2


def test_host_static_mount_keeps_working(client: TestClient) -> None:
    """
    Scenario: host static mount keeps working
      Given the host mounts its own /static before the admin is mounted
      When  the host stylesheet and the admin stylesheet are requested
      Then  /static/app.css is the host file
      And   the admin stylesheet is served under /admin/static
    """
    # Given the host mounts its own /static before the admin is mounted
    # When the host stylesheet and the admin stylesheet are requested
    host_css = client.get("/static/app.css")
    admin_css = client.get("/admin/static/css/hyperadmin.css")

    # Then /static/app.css is the host file
    assert host_css.status_code == 200
    assert "byoa host stylesheet" in host_css.text
    # And the admin stylesheet is served under /admin/static
    assert admin_css.status_code == 200


def test_anonymous_admin_request_redirects_to_host_login(client: TestClient) -> None:
    """
    Scenario: anonymous browser is sent to the host login page
      Given ExternalAuth(login_url="/login")
      When  GET /admin/project is requested without credentials
      Then  the response is 303 to /login?next=%2Fadmin%2Fproject
    """
    # Given ExternalAuth(login_url="/login")
    # When GET /admin/project is requested without credentials
    response = client.get("/admin/project", follow_redirects=False)

    # Then the response is 303 to /login?next=%2Fadmin%2Fproject
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fadmin%2Fproject"


def test_host_login_page_renders(client: TestClient) -> None:
    """
    Scenario: the host login page offers a labelled form
      Given the host serves its own /login page
      When  GET /login is requested
      Then  the page has Username and Password inputs and posts to /token
    """
    # Given the host serves its own /login page
    # When GET /login is requested
    response = client.get("/login")

    # Then the page has Username and Password inputs and posts to /token
    assert response.status_code == 200
    assert '<label for="username">Username</label>' in response.text
    assert '<label for="password">Password</label>' in response.text
    assert "/admin/auth/session" in response.text


def test_wrong_password_is_rejected_by_the_host(client: TestClient) -> None:
    """
    Scenario: the host token endpoint rejects a wrong password
      Given the seeded user ada
      When  POST /token is sent with a wrong password
      Then  the response is 401
    """
    # Given the seeded user ada
    # When POST /token is sent with a wrong password
    response = client.post("/token", data={"username": "ada", "password": "wrong"})

    # Then the response is 401
    assert response.status_code == 401


def test_host_api_is_jwt_protected(client: TestClient) -> None:
    """
    Scenario: the host API keeps its own JWT protection
      Given the host's /api/me route depends on the same get_current_user
      When  it is requested without and then with a bearer token
      Then  the first is 401 and the second returns ada
    """
    # Given the host's /api/me route depends on the same get_current_user
    token = _bearer(client)

    # When it is requested without and then with a bearer token
    anonymous = client.get("/api/me")
    authenticated = client.get("/api/me", headers=_auth(token))

    # Then the first is 401 and the second returns ada
    assert anonymous.status_code == 401
    assert authenticated.status_code == 200
    assert authenticated.json()["username"] == "ada"


def test_tampered_or_expired_token_is_anonymous(byoa: Any, client: TestClient) -> None:
    """
    Scenario: a tampered or expired JWT resolves no user
      Given a token signed with another key, an expired token and malformed ones,
            including a signature with a non-ASCII byte
      When  each is sent to /api/me
      Then  each response is 401
    """
    # Given a token signed with another key, an expired token and malformed ones,
    # including a signature with a non-ASCII byte
    from examples.byoa import auth

    forged = auth.issue_token("ada", secret="not-the-secret")
    expired = auth.issue_token("ada", ttl_seconds=-10)
    tokens = [forged.encode(), expired.encode(), b"not-a-jwt", b"a.b.c", b"a.b.\xe9"]

    # When each is sent to /api/me
    statuses = [
        client.get("/api/me", headers={"Authorization": b"Bearer " + t}).status_code for t in tokens
    ]

    # Then each response is 401
    assert statuses == [401, 401, 401, 401, 401]


def test_non_ascii_bearer_sends_the_browser_to_the_host_login(client: TestClient) -> None:
    """
    Scenario: a bearer with a non-ASCII signature is anonymous in the admin
      Given a bearer token whose signature segment contains a non-ASCII byte
      When  it is sent to /admin/
      Then  the browser is redirected to the host login page
    """
    # Given a bearer token whose signature segment contains a non-ASCII byte
    headers = {"Authorization": b"Bearer a.b.\xe9"}

    # When it is sent to /admin/
    response = client.get("/admin/", headers=headers, follow_redirects=False)

    # Then the browser is redirected to the host login page
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


@pytest.mark.parametrize(
    "stored",
    [
        "no-dollar-signs",
        "pbkdf2_sha256$many$salt$abcd",
        "pbkdf2_sha256$0$salt$abcd",
        "pbkdf2_sha256$-5$salt$abcd",
        f"pbkdf2_sha256${2**70}$salt$abcd",
        "pbkdf2_sha256$1$salt$\u00e9",
    ],
)
def test_malformed_password_hash_is_a_failed_check(byoa: Any, stored: str) -> None:
    """
    Scenario: a malformed stored password hash fails the check instead of erroring
      Given an account password_hash a superuser saved in a malformed shape
      When  the host verifies a password against it
      Then  the check returns False
    """
    # Given an account password_hash a superuser saved in a malformed shape
    from examples.byoa import auth

    # When the host verifies a password against it
    result = auth.verify_password("lovelace", stored)

    # Then the check returns False
    assert result is False


def test_hashed_password_round_trips(byoa: Any) -> None:
    """
    Scenario: a hash made by hash_password verifies the right password only
      Given a password hashed with hash_password
      When  the right and a wrong password are verified against it
      Then  only the right one passes
    """
    # Given a password hashed with hash_password
    from examples.byoa import auth

    stored = auth.hash_password("lovelace")

    # When the right and a wrong password are verified against it
    right = auth.verify_password("lovelace", stored)
    wrong = auth.verify_password("babbage", stored)

    # Then only the right one passes
    assert (right, wrong) == (True, False)


def test_admin_secret_key_comes_from_the_environment(byoa: Any) -> None:
    """
    Scenario: the example reads the admin secret key from HYPERADMIN_SECRET_KEY
      Given HYPERADMIN_SECRET_KEY is set when the example is imported
      When  the admin's settings are read
      Then  the admin signs with that key, not a hard-coded fallback
    """
    # Given HYPERADMIN_SECRET_KEY is set when the example is imported (byoa fixture)
    # When the admin's settings are read
    secret_key = byoa.admin.settings.secret_key

    # Then the admin signs with that key, not a hard-coded fallback
    assert secret_key == TEST_ADMIN_SECRET


def test_example_refuses_the_default_admin_secret_key(tmp_path: Path) -> None:
    """
    Scenario: the example refuses to start with the default admin secret key
      Given neither HYPERADMIN_SECRET_KEY nor HYPERADMIN_DEBUG is set
      When  examples.byoa.main is imported
      Then  the import fails with the admin's missing-secret-key error
    """
    # Given neither HYPERADMIN_SECRET_KEY nor HYPERADMIN_DEBUG is set
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYPERADMIN_")}
    env["PYTHONPATH"] = str(ROOT)

    # When examples.byoa.main is imported (from a directory without a .env file)
    result = subprocess.run(
        [sys.executable, "-c", "import examples.byoa.main"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    # Then the import fails with the admin's missing-secret-key error
    assert result.returncode != 0
    assert "no secret_key is configured" in result.stderr


def test_missing_host_secret_falls_back_with_a_warning(
    byoa: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a missing host secret uses the demo fallback and logs a warning
      Given BYOA_JWT_SECRET is not set
      When  the host reads it through demo_secret
      Then  the demo fallback is returned
      And   a warning naming BYOA_JWT_SECRET is logged
    """
    # Given BYOA_JWT_SECRET is not set
    from examples.byoa.config import demo_secret

    monkeypatch.delenv("BYOA_JWT_SECRET", raising=False)

    # When the host reads it through demo_secret
    with caplog.at_level(logging.WARNING, logger="examples.byoa.config"):
        value = demo_secret("BYOA_JWT_SECRET", "fallback-value")

    # Then the demo fallback is returned
    assert value == "fallback-value"
    # And a warning naming BYOA_JWT_SECRET is logged
    assert any("BYOA_JWT_SECRET" in r.getMessage() for r in caplog.records)


def test_set_host_secret_is_used_without_a_warning(
    byoa: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a set host secret is used as is
      Given BYOA_SESSION_SECRET is set
      When  the host reads it through demo_secret
      Then  the configured value is returned
      And   no warning is logged
    """
    # Given BYOA_SESSION_SECRET is set
    from examples.byoa.config import demo_secret

    monkeypatch.setenv("BYOA_SESSION_SECRET", "configured-value")

    # When the host reads it through demo_secret
    with caplog.at_level(logging.WARNING, logger="examples.byoa.config"):
        value = demo_secret("BYOA_SESSION_SECRET", "fallback-value")

    # Then the configured value is returned
    assert value == "configured-value"
    # And no warning is logged
    assert not caplog.records


def test_uuid_and_natural_str_models_render(byoa: Any, client: TestClient) -> None:
    """
    Scenario: UUID and natural-str primary keys render in the admin
      Given a Project with a UUID key and a Country with code "NL"
      When  both detail pages are requested with a valid bearer
      Then  both return 200
    """
    # Given a Project with a UUID key and a Country with code "NL"
    headers = _auth(_bearer(client))
    project_id = client.get("/api/projects", headers=headers).json()[0]["id"]
    assert uuid.UUID(project_id)

    # When both detail pages are requested with a valid bearer
    project = client.get(f"/admin/project/{project_id}", headers=headers)
    country = client.get("/admin/country/NL", headers=headers)

    # Then both return 200
    assert project.status_code == 200
    assert country.status_code == 200


def test_staff_user_is_view_only(client: TestClient) -> None:
    """
    Scenario: a staff user without has_permission is view-only
      Given grace is staff but not a superuser
      When  grace opens the project list and the create form
      Then  the list is 200 and the create form is 403
    """
    # Given grace is staff but not a superuser
    headers = _auth(_bearer(client, "grace", "hopper"))

    # When grace opens the project list and the create form
    listing = client.get("/admin/project", headers=headers)
    create = client.get("/admin/project/create", headers=headers)

    # Then the list is 200 and the create form is 403
    assert listing.status_code == 200
    assert create.status_code == 403


def test_host_user_password_hash_is_hidden(client: TestClient) -> None:
    """
    Scenario: the host user's password hash never reaches the admin
      Given the host Account model is registered in the admin
      When  ada opens the account list
      Then  no pbkdf2 hash is rendered
    """
    # Given the host Account model is registered in the admin
    headers = _auth(_bearer(client))

    # When ada opens the account list
    response = client.get("/admin/account", headers=headers)

    # Then no pbkdf2 hash is rendered
    assert response.status_code == 200
    assert "ada" in response.text
    assert "pbkdf2" not in response.text


# ── Scenario: token handoff and HTMX delete in bridge mode (unit-level) ────


def test_token_handoff_cookie_reaches_the_admin(client: TestClient) -> None:
    """
    Scenario: token handoff sets an admin-scoped cookie
      Given a valid bearer from the host's /token endpoint
      When  it is handed to POST /admin/auth/session
      Then  hyperadmin_token is set with Path=/admin
      And   GET /admin/ with only that cookie returns 200
    """
    # Given a valid bearer from the host's /token endpoint
    token = _bearer(client)

    # When it is handed to POST /admin/auth/session
    handoff = client.post("/admin/auth/session", headers=_auth(token))

    # Then hyperadmin_token is set with Path=/admin
    assert handoff.status_code == 204
    cookie = next(c for c in _set_cookies(handoff) if c.startswith("hyperadmin_token="))
    assert "Path=/admin" in cookie
    assert "HttpOnly" in cookie
    # And GET /admin/ with only that cookie returns 200
    assert client.get("/admin/").status_code == 200


def test_htmx_delete_with_handoff_cookie(byoa: Any, client: TestClient) -> None:
    """
    Scenario: HTMX delete in bridge mode
      Given a token cookie from the handoff and the CSRF token of a rendered page
      When  an HTMX DELETE is sent for a project
      Then  the response is 200
      And   the project is gone
    """
    # Given a token cookie from the handoff and the CSRF token of a rendered page
    token = _bearer(client)
    client.post("/admin/auth/session", headers=_auth(token))
    page = client.get("/admin/project")
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', page.text)
    assert match is not None
    project_id = client.get("/api/projects", headers=_auth(token)).json()[-1]["id"]

    # When an HTMX DELETE is sent for a project
    response = client.delete(
        f"/admin/project/{project_id}",
        headers={"HX-Request": "true", "X-CSRF-Token": match.group(1)},
    )

    # Then the response is 200
    assert response.status_code == 200
    # And the project is gone
    assert client.get(f"/admin/project/{project_id}").status_code == 404


def test_logout_clears_token_cookie(client: TestClient) -> None:
    """
    Scenario: admin logout clears the token cookie
      Given a token cookie from the handoff
      When  the user posts the admin logout with the CSRF token
      Then  the response redirects to the host home page
      And   hyperadmin_token is cleared
    """
    # Given a token cookie from the handoff
    client.post("/admin/auth/session", headers=_auth(_bearer(client)))
    page = client.get("/admin/")
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', page.text)
    assert match is not None

    # When the user posts the admin logout with the CSRF token
    response = client.post(
        "/admin/logout", headers={"X-CSRF-Token": match.group(1)}, follow_redirects=False
    )

    # Then the response redirects to the host home page
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    # And hyperadmin_token is cleared
    assert any(c.startswith('hyperadmin_token=""') for c in _set_cookies(response))


# ── Scenario: guide under 20 lines ──────────────────────────────────────────


def _wiring_snippet() -> str:
    text = GUIDE.read_text(encoding="utf-8")
    _, marker, rest = text.partition(WIRING_MARKER)
    assert marker, f"{GUIDE} must mark its minimal wiring snippet with {WIRING_MARKER}"
    match = re.search(r"```python\n(.*?)```", rest, re.DOTALL)
    assert match is not None
    return match.group(1)


def test_guide_wiring_snippet_is_under_20_lines() -> None:
    """
    Scenario: guide under 20 lines
      Given the guide's minimal wiring snippet
      When  it is counted
      Then  it is fewer than 20 lines of code
    """
    # Given the guide's minimal wiring snippet
    snippet = _wiring_snippet()

    # When it is counted
    code_lines = [
        line for line in snippet.splitlines() if line.strip() and not line.strip().startswith("#")
    ]

    # Then it is fewer than 20 lines of code
    assert 0 < len(code_lines) < MAX_WIRING_LINES
    ast.parse(snippet)
    assert "ExternalAuth(" in snippet
    assert "session_factory=" in snippet
    assert '.mount("/admin")' in snippet


def test_guides_are_in_the_docs_nav() -> None:
    """
    Scenario: the new guides are reachable from the docs site
      Given zensical.toml configures the docs navigation
      When  its nav is read
      Then  it lists guides/existing-app.md and guides/external-auth.md
    """
    # Given zensical.toml configures the docs navigation
    nav = NAV.read_text(encoding="utf-8")

    # When its nav is read / Then it lists both guides
    assert '"guides/existing-app.md"' in nav
    assert '"guides/external-auth.md"' in nav


# ── Review amendments ───────────────────────────────────────────────────────


def test_guide_covers_bearer_only_hosts_and_realtime_lifespan() -> None:
    """
    Scenario: the guides cover bearer-only hosts and realtime shutdown
      Given the existing-app and external-auth guides
      When  they are read
      Then  they show TokenCookie(token_endpoint=...) for bearer-only hosts
      And   they tell realtime users to compose admin.lifespan()
    """
    # Given the existing-app and external-auth guides
    # When they are read
    guides = GUIDE.read_text(encoding="utf-8") + AUTH_GUIDE.read_text(encoding="utf-8")

    # Then they show TokenCookie(token_endpoint=...) for bearer-only hosts
    assert "TokenCookie(token_endpoint=" in guides
    # And they tell realtime users to compose admin.lifespan()
    assert "async with admin.lifespan():" in guides
    assert "realtime" in guides.lower()


def test_changelog_upgrade_note_covers_proxy_permissions_and_sensitive_fields() -> None:
    """
    Scenario: the upgrade note covers TLS proxies, bridge permissions and sensitive fields
      Given the 0.5.0a1 changelog section
      When  its upgrade note is read
      Then  it has a TLS proxy section naming the Origin rule and its settings
      And   it covers CSRF report mode, fail-safe bridge permissions and sensitive fields
    """
    # Given the 0.5.0a1 changelog section
    text = CHANGELOG.read_text(encoding="utf-8")
    section = text.split("## [0.5.0a1]", 1)[1].split("\n## [", 1)[0]

    # When its upgrade note is read
    _, heading, note = section.partition("### Upgrade note")
    assert heading
    note = note.split("\n### ", 1)[0]

    # Then it has a TLS proxy section naming the Origin rule and its settings
    assert "TLS" in note
    for needle in ("Origin", "csrf_trusted_origins", "HYPERADMIN_COOKIE_SECURE=true"):
        assert needle in note
    assert "forwarded_allow_ips" in note
    # And it covers CSRF report mode, fail-safe bridge permissions and sensitive fields
    for needle in ("HYPERADMIN_CSRF_MODE=report", "csrf_input()", "allow_full_access"):
        assert needle in note
    assert "sensitive_fields" in note
    assert "admin.lifespan()" in note


def test_multi_tenancy_sdd_resolves_tenant_after_the_admin_principal() -> None:
    """
    Scenario: the multi-tenancy SDD is amended for bridge mode
      Given docs/specs/multi-tenancy.md
      When  its BYOA amendment is read
      Then  tenants are resolved in a route dependency after the admin principal
      And   ModelAdmin.get_queryset is the alternative that works in both auth modes
    """
    # Given docs/specs/multi-tenancy.md
    text = TENANCY_SDD.read_text(encoding="utf-8")

    # When its BYOA amendment is read
    _, heading, amendment = text.partition("## Amendment: bring your own app")
    assert heading

    # Then tenants are resolved in a route dependency after the admin principal
    assert "route dependency" in amendment
    assert "build_admin_dependency" in amendment
    # And ModelAdmin.get_queryset is the alternative that works in both auth modes
    assert "ModelAdmin.get_queryset" in amendment
    assert "bring-your-own-app.md" in amendment

"""E2E: CSRF enforcement under built-in auth ships with token injection (SDD D.1).

st-v058-byoa-39 and st-v058-byoa-46. Uses the object-permission app (built-in
``SessionAuthBackend``, default ``csrf_mode="auto"`` so CSRF is enforced) and the
bridge-mode app (``Admin(auth=ExternalAuth(...))``). One test per scenario.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def test_plain_form_post_uses_the_hidden_csrf_field(page: Page, object_perm_base_url: str) -> None:
    """
    Scenario: plain form post uses the hidden csrf field
      Given the login page rendered a hidden csrf_token input
      When  the user submits valid credentials through the form
      Then  the browser lands on the dashboard
    """
    # Given the login page rendered a hidden csrf_token input
    page.goto(f"{object_perm_base_url}/admin/login")
    form = page.get_by_test_id("login-form")
    expect(form.locator('input[type="hidden"][name="csrf_token"]')).to_have_count(1)

    # When the user submits valid credentials through the form
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()

    # Then the browser lands on the dashboard
    expect(page).to_have_url(f"{object_perm_base_url}/admin/")


def test_csrf_injection_ships_with_enforcement(page: Page, object_perm_base_url: str) -> None:
    """
    Scenario: CSRF injection ships with enforcement
      Given built-in auth and the default csrf_mode
      When  a logged-in user saves a record from the rendered edit page
      Then  the request carries X-CSRF-Token and succeeds
    """
    # Given built-in auth and the default csrf_mode, a logged-in superuser
    _login(page, object_perm_base_url)
    page.goto(f"{object_perm_base_url}/admin/order/20/edit")

    # When the user saves the record through the page's own HTMX request
    page.get_by_label("Title").fill("bob-order-B (edited)")
    with page.expect_response(lambda r: r.request.method == "PUT") as response_info:
        page.get_by_role("button", name="Update").click()
    response = response_info.value

    # Then the request carries X-CSRF-Token and succeeds
    assert response.request.headers.get("x-csrf-token")
    assert response.status == 200
    page.goto(f"{object_perm_base_url}/admin/order/20")
    expect(page.get_by_role("heading", name="bob-order-B (edited)")).to_be_visible()


def test_htmx_unsafe_request_without_a_token_is_rejected(
    page: Page, object_perm_base_url: str
) -> None:
    """
    Scenario: HTMX unsafe request without a CSRF token is rejected
      Given a logged-in built-in session user
      When  DELETE /admin/order/20 is sent with HX-Request and no X-CSRF-Token header
      Then  the response is 403 with X-HyperAdmin-CSRF: failed
      And   order 20 still exists
    """
    # Given a logged-in built-in session user
    _login(page, object_perm_base_url)

    # When DELETE is sent with HX-Request and no X-CSRF-Token header
    response = page.request.delete(
        f"{object_perm_base_url}/admin/order/20", headers={"HX-Request": "true"}
    )

    # Then the response is 403 with X-HyperAdmin-CSRF: failed
    assert response.status == 403
    assert response.headers.get("x-hyperadmin-csrf") == "failed"
    # And order 20 still exists
    page.goto(f"{object_perm_base_url}/admin/order/20")
    expect(page.get_by_test_id("detail-fields")).to_be_visible()


# ---------------------------------------------------------------------------
# st-v058-byoa-46: bridge-aware navbar and the CSRF reload banner
# ---------------------------------------------------------------------------


def test_htmx_delete_carries_token(page: Page, object_perm_base_url: str) -> None:
    """
    Scenario: HTMX delete carries token
      Given the list page rendered with body hx-headers
      When  the delete button issues DELETE /admin/order/10
      Then  the response is 200
      And   order 10 is deleted
    """
    # Given the list page rendered with body hx-headers
    _login(page, object_perm_base_url)
    page.goto(f"{object_perm_base_url}/admin/order/")
    row = page.get_by_test_id("list-row").filter(has_text="bob-order-A")
    expect(row).to_have_count(1)

    # When the delete button issues DELETE /admin/order/10
    page.on("dialog", lambda dialog: dialog.accept())
    with page.expect_response(lambda r: r.request.method == "DELETE") as response_info:
        row.get_by_test_id("row-delete-btn").click()
    response = response_info.value

    # Then the response is 200
    assert response.request.headers.get("x-csrf-token")
    assert response.status == 200
    # And order 10 is deleted
    assert page.request.get(f"{object_perm_base_url}/admin/order/10").status == 404


def test_login_csrf_blocked(page: Page, object_perm_base_url: str) -> None:
    """
    Scenario: login CSRF blocked
      Given no hyperadmin_csrf cookie
      When  a cross-site form POSTs /admin/login
      Then  the response is 403
      And   no session is created
    """
    # Given no hyperadmin_csrf cookie (a fresh browser context)
    assert not [c for c in page.context.cookies() if c["name"] == "hyperadmin_csrf"]

    # When a cross-site form POSTs /admin/login
    response = page.request.post(
        f"{object_perm_base_url}/admin/login",
        form={"username": "admin", "password": "secret123"},
        headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
        max_redirects=0,
    )

    # Then the response is 403
    assert response.status == 403
    assert response.headers.get("x-hyperadmin-csrf") == "failed"
    # And no session is created: the dashboard still redirects to the login page
    page.goto(f"{object_perm_base_url}/admin/")
    expect(page).to_have_url(f"{object_perm_base_url}/admin/login")


def test_stale_token_banner(page: Page, object_perm_base_url: str) -> None:
    """
    Scenario: stale token banner
      Given a stale CSRF cookie
      When  an HTMX unsafe request gets 403 with X-HyperAdmin-CSRF
      Then  get_by_test_id('csrf-reload-banner') is visible
    """
    _login(page, object_perm_base_url)
    page.goto(f"{object_perm_base_url}/admin/order/")
    banner = page.get_by_test_id("csrf-reload-banner")
    expect(banner).to_be_hidden()

    # Given a stale CSRF cookie: the page's token no longer matches the cookie
    stale = []
    for cookie in page.context.cookies():
        if cookie["name"] == "hyperadmin_csrf":
            cookie["value"] = "stale.token"
            stale.append(cookie)
    assert stale
    page.context.add_cookies(stale)  # type: ignore[arg-type]

    # When an HTMX unsafe request gets 403 with X-HyperAdmin-CSRF
    page.on("dialog", lambda dialog: dialog.accept())
    row = page.get_by_test_id("list-row").filter(has_text="bob-order-A")
    with page.expect_response(lambda r: r.request.method == "DELETE") as response_info:
        row.get_by_test_id("row-delete-btn").click()
    assert response_info.value.status == 403
    assert response_info.value.headers.get("x-hyperadmin-csrf") == "failed"

    # Then get_by_test_id('csrf-reload-banner') is visible
    expect(banner).to_be_visible()
    expect(banner.get_by_role("button", name="Reload page")).to_be_visible()


def test_bridged_navbar(page: Page, bridge_base_url: str) -> None:
    """
    Scenario: bridged navbar
      Given a bridged user with display name 'Ada'
      When  the dashboard renders
      Then  the navbar shows 'Ada'
    """
    # Given a bridged user with display name 'Ada' (the host's own session cookie)
    page.context.add_cookies([{"name": "host_user", "value": "ada", "url": bridge_base_url}])

    # When the dashboard renders
    page.goto(f"{bridge_base_url}/admin/")

    # Then the navbar shows 'Ada'
    expect(page.get_by_test_id("current-user")).to_have_text("Ada")

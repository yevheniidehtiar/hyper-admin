"""E2E: CSRF enforcement under built-in auth ships with token injection (SDD D.1).

st-v058-byoa-39. Uses the object-permission app (built-in ``SessionAuthBackend``,
default ``csrf_mode="auto"`` so CSRF is enforced). One test per scenario.
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

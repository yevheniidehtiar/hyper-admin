import re

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def debug_page(page: Page):
    network_logs = []

    def parse_body(_response):
        try:
            return _response.text() if _response.status < 400 else f"Error:{_response.status}"
        except Exception:
            return _response.content

    page.on("request", lambda _r: print(f"Request: {_r.method} {_r.url}"))
    page.on(
        "response",
        lambda _r: network_logs.append(
            {
                "url": _r.url,
                "status": _r.status,
                "headers": _r.all_headers(),
                "body": parse_body(_r),
            }
        ),
    )
    yield page
    print(f"Network logs: {network_logs}")


def test_create_user_form_rendering(page: Page, demo_base_url: str):
    page.goto(f"{demo_base_url}/admin/user/create")
    expect(page).to_have_title("HyperAdmin")
    expect(page.get_by_role("heading", name="Create User")).to_be_visible()
    expect(page.get_by_test_id("model-form")).to_be_visible()
    expect(page.get_by_label("Name*")).to_be_visible()
    expect(page.get_by_label("Email*")).to_be_visible()
    expect(page.get_by_label("Is active*")).to_be_visible()
    expect(page.get_by_label("Rating*")).to_be_visible()
    expect(page.get_by_label("User type*")).to_be_visible()
    expect(page.get_by_role("button", name="Create")).to_be_visible()


def test_create_user_validation_error(page: Page, demo_base_url: str):
    page.goto(f"{demo_base_url}/admin/user/create")
    page.get_by_label("Name*").fill("")
    page.get_by_role("button", name="Create").click()
    error_list = page.get_by_test_id("name-errors")
    expect(error_list).to_be_visible()
    expect(error_list).to_contain_text("String should have at least 1 character")


def test_create_user_successful_submission(debug_page: Page, demo_base_url: str):
    page = debug_page
    page.goto(f"{demo_base_url}/admin/user/create")
    page.get_by_label("Name*").fill("Test User")
    page.get_by_label("Email*").fill("test@example.com")
    page.get_by_label("Is active*").check()
    page.get_by_label("Rating*").fill("4.5")
    page.get_by_label("User type*").select_option("ADMIN")
    page.get_by_role("button", name="Create").click()
    expect(page).to_have_url(re.compile(r".*/admin/user/\d+"))
    expect(page.get_by_role("heading", name=re.compile(r"Test User"))).to_contain_text("Test User")
    detail = page.get_by_test_id("detail-fields")
    expect(detail).to_contain_text("Test User")
    expect(detail).to_contain_text("test@example.com")
    expect(detail).to_contain_text("True")
    expect(detail).to_contain_text("4.5")
    expect(detail).to_contain_text("UserType.ADMIN")
    expect(detail).to_contain_text("created_at")

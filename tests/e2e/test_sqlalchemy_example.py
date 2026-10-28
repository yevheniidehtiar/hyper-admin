"""E2E smoke for the plain SQLAlchemy example app (#730, SDD sqlalchemy-field-metadata).

Boots ``examples/sqlalchemy`` (a ``DeclarativeBase`` app, no SQLModel) and drives the
list, create and edit pages for its ``Project`` model.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def sqlalchemy_base_url(start_server: Callable[..., str]) -> str:
    """Start the SQLAlchemy example app via uvicorn and return the base URL."""
    return start_server("tests.e2e.apps.sqlalchemy_example", ready_path="/")


def test_list_page_renders_for_a_plain_sqlalchemy_model(
    page: Page, sqlalchemy_base_url: str
) -> None:
    """Scenario: list page renders for a plain SQLAlchemy model."""
    # Given the sqlalchemy example app with seeded rows
    # (the app seeds three projects on startup)

    # When the list page for a plain DeclarativeBase model is opened
    page.goto(f"{sqlalchemy_base_url}/admin/project")

    # Then the list table shows the seeded rows
    expect(page.get_by_test_id("list-table")).to_be_visible()
    expect(page.get_by_test_id("list-row")).to_have_count(3)
    expect(page.get_by_role("cell", name="Website", exact=True)).to_be_visible()
    expect(page.get_by_role("cell", name="Backend", exact=True)).to_be_visible()
    expect(page.get_by_role("cell", name="Mobile", exact=True)).to_be_visible()


def test_create_round_trips_through_the_form(page: Page, sqlalchemy_base_url: str) -> None:
    """Scenario: create round-trips through the form."""
    # Given the sqlalchemy example app
    page.goto(f"{sqlalchemy_base_url}/admin/project/create")

    # When the create form is filled with valid values and submitted
    page.get_by_label("Name").fill("Roadmap")
    page.get_by_label("Note").fill("Q4 planning")
    page.get_by_label("Status").select_option("active")
    page.get_by_label("Priority").select_option("high")
    page.get_by_role("button", name="Create").click()

    # Then the form redirects to the new row's detail page
    page.wait_for_url(re.compile(r"/admin/project/\d+$"))

    # And the new row appears in the list
    page.goto(f"{sqlalchemy_base_url}/admin/project")
    expect(page.get_by_test_id("list-row")).to_have_count(4)
    expect(page.get_by_role("cell", name="Roadmap", exact=True)).to_be_visible()


def test_edit_form_shows_the_saved_values(page: Page, sqlalchemy_base_url: str) -> None:
    """Scenario: edit form shows the saved values."""
    # Given an existing row (the seeded "Website" project: id 1)

    # When its edit page is opened
    page.goto(f"{sqlalchemy_base_url}/admin/project/1/edit")

    # Then every editable column is pre-filled with the saved value
    expect(page.get_by_label("Name")).to_have_value("Website")
    expect(page.get_by_label("Note")).to_have_value("Public site")
    expect(page.get_by_label("Status")).to_have_value("active")
    expect(page.get_by_label("Priority")).to_have_value("high")
    expect(page.get_by_label("Payload")).to_have_value(re.compile(r"web"))
    expect(page.get_by_test_id("autocomplete-select-org_id")).to_have_value("1")

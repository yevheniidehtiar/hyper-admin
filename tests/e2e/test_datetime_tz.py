"""End-to-end tests for timezone-aware datetimes (BYOA SDD, BDD scenarios: Datetimes).

Runs against :mod:`tests.e2e.apps.pk_types`, started with
``HYPERADMIN_TIMEZONE=Europe/Amsterdam``. ``Event.starts_at`` is an aware
column stored as naive UTC; the app's ``/_test/events`` host route returns
what the database actually holds.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_timezone_round_trip(page: Page, pk_types_base_url: str) -> None:
    """
    Scenario: timezone round-trip
      Given HYPERADMIN_TIMEZONE=Europe/Amsterdam
      When  the user enters 10:00
      Then  the list shows 10:00
      And   the DB holds 08:00Z
    """
    # Given HYPERADMIN_TIMEZONE=Europe/Amsterdam (set by the fixture)
    page.goto(pk_types_base_url + "/admin/event/create")
    expect(page.get_by_test_id("starts_at-tz")).to_contain_text("Europe/Amsterdam")

    # When the user enters 10:00 on 2026-07-01 (CEST, UTC+2)
    page.get_by_label("Title").fill("Launch")
    page.get_by_label("Starts at").fill("2026-07-01T10:00")
    page.get_by_role("button", name="Create").click()
    expect(page).to_have_url(re.compile(r"/admin/event/\d+$"))

    # Then the list shows 10:00
    page.goto(pk_types_base_url + "/admin/event")
    row = page.get_by_test_id("list-row").filter(has_text="Launch")
    expect(row).to_contain_text("2026-07-01 10:00")

    # And the DB holds 08:00Z (naive UTC text, as SQLAlchemy writes it to SQLite)
    stored = page.request.get(pk_types_base_url + "/_test/events").json()
    assert stored == [{"title": "Launch", "starts_at": "2026-07-01 08:00:00.000000"}]

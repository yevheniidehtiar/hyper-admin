"""Per-user pinned pages in the sidebar (story st-v059-nav-03).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Data Model Changes", "API / Protocol
Changes", "UI details", "Edge Cases").
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from starlette.requests import Request

import hyperadmin.auth
from hyperadmin import Admin, NavGroup
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.navigation import NavPin, NavPinService, PinLimitError
from hyperadmin.views.nav_pins import NavPins
from tests.conftest import with_csrf

HTML = {"accept": "text/html"}
HX = {"hx-request": "true"}
SECRET = "x" * 40


class NpOrder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)


class NpInvoice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)


class NpOrderAdmin(ModelAdmin):
    name_plural = "Orders"
    nav_group = "Sales"


class NpInvoiceAdmin(ModelAdmin):
    name_plural = "Invoices"
    nav_group = "Accounting"


@dataclass
class _User:
    id: int
    username: str
    is_superuser: bool = False


class _Backend:
    """Signs in whoever the ``x-user`` header names (alice by default)."""

    users = {"alice": _User(1, "alice"), "bob": _User(2, "bob")}

    async def get_current_user(self, request: Any) -> _User:
        return self.users[request.headers.get("x-user", "alice")]

    async def authenticate(self, username: str, password: str) -> None:
        return None


class _Checker:
    granted: dict[str, set[str]] = {}

    async def has_permission(self, user: Any, codename: str) -> bool:
        return codename in self.granted.get(user.username, set())

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set(self.granted.get(user.username, set()))


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    _Checker.granted = {
        "alice": {"view_nporder", "view_npinvoice"},
        "bob": {"view_nporder", "view_npinvoice"},
    }
    yield
    site._registry = {}


def _engine(*, with_pins: bool = True) -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [NpOrder.__table__, NpInvoice.__table__]  # type: ignore[attr-defined]
    if with_pins:
        tables.append(NavPin.__table__)  # type: ignore[attr-defined]

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all, tables=tables)

    anyio.run(_setup)
    return engine


def _admin(
    *, auth: bool = True, with_pins: bool = True, **settings: Any
) -> tuple[Admin, TestClient]:
    engine = _engine(with_pins=with_pins)
    app = FastAPI()
    extra: dict[str, Any] = {}
    if auth:
        extra = {"auth_backend": _Backend(), "permission_checker": _Checker()}
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key=SECRET, **settings),
        nav_groups=[NavGroup("Sales"), NavGroup("Accounting")],
        **extra,
    )
    site.register(NpOrder, NpOrderAdmin)
    site.register(NpInvoice, NpInvoiceAdmin)
    admin.mount(path="/admin")
    client = TestClient(app)
    return admin, with_csrf(client, SECRET) if auth else client


def _pin(client: TestClient, target: str, user: str = "alice") -> Any:
    return client.post("/admin/nav/pins", data={"target": target}, headers={**HX, "x-user": user})


def _pinned_group(html: str) -> str:
    start = html.find('data-testid="nav-pinned"')
    return "" if start == -1 else html[start : html.index("</ul>", start)]


def _toggle(html: str, key: str) -> str:
    match = re.search(rf'<button[^>]*data-testid="nav-pin-{key}"[^>]*>', html)
    assert match, f"no pin toggle for {key!r}"
    return match.group(0)


# -- scenarios ---------------------------------------------------------------------


def test_pinning_a_model_adds_it_to_the_pinned_group() -> None:
    """
    Scenario: pinning a model adds it to the Pinned group
      Given alice is signed in with no pins
      When  alice pins Orders
      Then  the Pinned group shows Orders and the toggle has aria-pressed="true"
    """
    _, client = _admin()
    page = client.get("/admin/", headers=HTML).text
    assert 'data-testid="nav-pinned"' not in page
    assert 'aria-pressed="false"' in _toggle(page, "nporder")
    assert 'aria-label="Pin Orders"' in _toggle(page, "nporder")

    response = _pin(client, "nporder")

    assert response.status_code == 200
    assert 'href="/admin/nporder"' in _pinned_group(response.text)
    oob = _toggle(response.text, "nporder")
    assert 'aria-pressed="true"' in oob
    assert 'hx-swap-oob="true"' in oob
    assert 'hx-delete="/admin/nav/pins/nporder"' in oob
    page = client.get("/admin/", headers=HTML).text
    assert 'href="/admin/nporder"' in _pinned_group(page)
    assert 'aria-label="Unpin Orders"' in _toggle(page, "nporder")


def test_pins_follow_the_user_to_another_browser() -> None:
    """
    Scenario: pins follow the user to another browser
      Given alice pinned Orders
      When  alice signs in from a new browser context
      Then  Orders is in her Pinned group
    """
    admin, client = _admin()
    assert _pin(client, "nporder").status_code == 200

    fresh = with_csrf(TestClient(admin.app), SECRET)
    page = fresh.get("/admin/", headers=HTML).text

    assert 'href="/admin/nporder"' in _pinned_group(page)


def test_pins_are_per_user() -> None:
    """
    Scenario: pins are per user
      Given alice pinned Orders
      When  bob opens the dashboard
      Then  bob has no Pinned group
    """
    _, client = _admin()
    _pin(client, "nporder")

    page = client.get("/admin/", headers={**HTML, "x-user": "bob"}).text

    assert 'data-testid="nav-pinned"' not in page
    assert 'aria-pressed="false"' in _toggle(page, "nporder")


def test_a_pin_the_user_can_no_longer_view_is_hidden() -> None:
    """
    Scenario: a pin the user can no longer view is hidden
      Given alice pinned Invoices and then loses view_invoice
      When  alice opens the dashboard
      Then  Invoices is not shown in Pinned
      And   it shows again once the permission returns (the pin row is kept)
    """
    _, client = _admin()
    _pin(client, "nporder")
    _pin(client, "npinvoice")
    _Checker.granted["alice"] = {"view_nporder"}

    page = client.get("/admin/", headers=HTML).text

    pinned = _pinned_group(page)
    assert 'href="/admin/nporder"' in pinned
    assert "npinvoice" not in pinned
    assert 'data-testid="nav-npinvoice"' not in page
    _Checker.granted["alice"] = {"view_nporder", "view_npinvoice"}
    assert 'href="/admin/npinvoice"' in _pinned_group(client.get("/admin/", headers=HTML).text)


def test_unknown_or_forbidden_pin_targets_return_404() -> None:
    """
    Scenario: unknown or forbidden pin targets return 404
      When  alice POSTs target="secretmodel"
      Then  the response is 404
      And   so is a model she may not view, or an unpin of either
    """
    _, client = _admin()
    _Checker.granted["alice"] = {"view_nporder"}

    assert _pin(client, "secretmodel").status_code == 404
    assert _pin(client, "npinvoice").status_code == 404
    assert client.post("/admin/nav/pins", headers=HX).status_code == 404
    assert client.delete("/admin/nav/pins/npinvoice", headers=HX).status_code == 404


def test_a_pin_beyond_the_limit_is_refused() -> None:
    """
    Scenario: a pin beyond the limit is refused
      Given nav_pins_max is 1 and alice has 1 pin
      When  alice pins another page
      Then  the response is 409 and an error toast explains the limit
      And   pinning the page she already pinned is still fine
    """
    _, client = _admin(nav_pins_max=1)
    assert _pin(client, "nporder").status_code == 200

    refused = _pin(client, "npinvoice")

    assert refused.status_code == 409
    assert "You can pin up to 1 pages" in refused.text
    assert refused.headers["HX-Retarget"] == ".ha-toast-container"
    assert _pin(client, "nporder").status_code == 200


def test_no_auth_means_no_pins() -> None:
    """
    Scenario: no auth means no pins
      Given HyperAdmin without auth
      When  the dashboard renders
      Then  no pin toggles are rendered and /nav/pins is not routed
    """
    _, client = _admin(auth=False)

    page = client.get("/admin/", headers=HTML).text

    assert 'data-testid="nav-pin-' not in page
    assert 'id="ha-nav-pinned"' not in page
    assert client.post("/admin/nav/pins", data={"target": "nporder"}).status_code == 404


# -- edge cases --------------------------------------------------------------------


def test_unpin_removes_the_pin_and_is_idempotent() -> None:
    """
    Scenario: unpinning empties the Pinned group
      Given alice pinned Orders
      When  alice unpins it twice
      Then  both calls answer 200 with an empty Pinned slot and a "Pin Orders" toggle
    """
    _, client = _admin()
    _pin(client, "nporder")

    first = client.delete("/admin/nav/pins/nporder", headers=HX)
    second = client.delete("/admin/nav/pins/nporder", headers=HX)

    for response in (first, second):
        assert response.status_code == 200
        assert 'id="ha-nav-pinned"' in response.text
        assert 'data-testid="nav-pinned"' not in response.text
        assert 'aria-label="Pin Orders"' in _toggle(response.text, "nporder")


def test_pin_endpoints_refuse_a_request_without_a_user_key() -> None:
    """
    Scenario: a pin request reaches the view without a signed-in user
      Given a request whose state has no user_key
      When  the pin view resolves the owner
      Then  it answers 403
    """
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

    with pytest.raises(HTTPException) as exc:
        NavPins._user(request)

    assert exc.value.status_code == 403


def test_csrf_is_enforced_on_pin_requests() -> None:
    _, client = _admin()
    bare = TestClient(client.app)

    response = bare.post("/admin/nav/pins", data={"target": "nporder"}, headers=HX)

    assert response.status_code == 403


def test_missing_table_is_logged_once_and_hides_pins(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: the host has not created hyperadmin_nav_pin yet
      Given auth is on and the pins table is missing
      When  two pages render and a pin is posted
      Then  both pages render without toggles, the POST is 404, and one warning names the table
    """
    _, client = _admin(with_pins=False)

    with caplog.at_level(logging.WARNING, logger="hyperadmin.views.nav_pins"):
        pages = [client.get("/admin/", headers=HTML) for _ in range(2)]
        posted = _pin(client, "nporder")
        unpinned = client.delete("/admin/nav/pins/nporder", headers=HX)

    assert all(p.status_code == 200 and "nav-pin-" not in p.text for p in pages)
    assert (posted.status_code, unpinned.status_code) == (404, 404)
    warnings = [r for r in caplog.records if "hyperadmin_nav_pin" in r.getMessage()]
    assert len(warnings) == 1


def test_htmx_partials_and_posts_do_not_load_pins() -> None:
    """
    Scenario: only full pages query the pins
      Given alice pinned Orders
      When  an HTMX partial of the list is requested
      Then  it carries no Pinned group (the pins were not loaded)
    """
    admin, client = _admin()
    _pin(client, "nporder")
    calls: list[Any] = []
    service = admin._nav_pins.service  # type: ignore[union-attr]
    original = service.list_for

    async def counting(user_key: Any) -> list[str]:
        calls.append(user_key)
        return await original(user_key)

    service.list_for = counting  # type: ignore[method-assign]
    client.get("/admin/nporder", headers={**HTML, **HX})
    assert calls == []
    client.get("/admin/nporder", headers={**HTML, **HX, "hx-boosted": "true"})
    assert calls == [1]


def test_nav_pins_max_setting() -> None:
    """
    Scenario: nav_pins_max defaults to 20 and must be at least 1
      Given HyperAdminSettings
      When  it is built with defaults, from HYPERADMIN_NAV_PINS_MAX, or with 0
      Then  the limit is 20, the env value, or a validation error
    """
    assert HyperAdminSettings().nav_pins_max == 20
    with pytest.raises(ValidationError):
        HyperAdminSettings(nav_pins_max=0)


def test_nav_pins_max_reads_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HYPERADMIN_NAV_PINS_MAX", "5")

    assert HyperAdminSettings().nav_pins_max == 5


def test_the_table_is_part_of_the_hyperadmin_metadata() -> None:
    """
    Scenario: init-db and Alembic hosts see the pins table
      Given hyperadmin.auth.metadata()
      When  it is built
      Then  it holds hyperadmin_nav_pin with the (user_key, target) unique constraint
    """
    table = hyperadmin.auth.metadata().tables["hyperadmin_nav_pin"]

    assert {c.name for c in table.columns} == {"id", "user_key", "target", "created_at"}
    assert [c.name for c in table.constraints if c.name == "uq_hyperadmin_nav_pin"]


# -- service -----------------------------------------------------------------------


def _service(**kwargs: Any) -> NavPinService:
    return NavPinService(_engine(), **kwargs)


def test_service_lists_pins_in_pin_order_per_user() -> None:
    """
    Scenario: pins are listed in the order they were pinned
      Given alice pins b, then a; bob pins c
      When  each user's pins are listed
      Then  alice gets [b, a] and bob [c]; pinning b again changes nothing
    """
    service = _service()

    async def run() -> None:
        assert await service.pin(1, "b") is True
        assert await service.pin("1", "a") is True
        assert await service.pin(2, "c") is True
        assert await service.pin(1, "b") is False
        assert await service.list_for(1) == ["b", "a"]
        assert await service.list_for(2) == ["c"]

    anyio.run(run)


def test_service_default_limit_is_twenty() -> None:
    """
    Scenario: a pin beyond the default limit is refused
      Given nav_pins_max is 20 (default) and alice has 20 pins
      When  alice pins another page
      Then  PinLimitError(20) is raised
    """
    service = _service()

    async def run() -> None:
        for n in range(20):
            await service.pin(1, f"page{n}")
        with pytest.raises(PinLimitError) as exc:
            await service.pin(1, "one-more")
        assert exc.value.limit == 20
        assert str(exc.value) == "You can pin up to 20 pages"

    anyio.run(run)


def test_service_deletes_stale_pins_on_the_next_change() -> None:
    """
    Scenario: a pin whose target is gone is deleted on the next pin or unpin
      Given alice pinned "gone" and "order"
      When  she pins "invoice" with known={"order", "invoice"}
      Then  "gone" is deleted and does not count towards the limit
    """
    service = _service(max_pins=2)

    async def run() -> None:
        await service.pin(1, "gone")
        await service.pin(1, "order")
        assert await service.pin(1, "invoice", known={"order", "invoice"}) is True
        assert await service.list_for(1) == ["order", "invoice"]
        assert await service.unpin(1, "order", known={"order", "invoice"}) is True
        assert await service.unpin(1, "order") is False
        assert await service.list_for(1) == ["invoice"]

    anyio.run(run)


def test_service_treats_a_unique_violation_as_already_pinned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: a double click races past the existence check
      Given the existence check misses a pin that is already stored
      When  the same target is pinned again
      Then  the unique constraint fires and pin() returns False, keeping one row
    """
    service = _service()

    async def never_pinned(*_args: Any) -> bool:
        return False

    async def run() -> None:
        await service.pin(1, "order")
        monkeypatch.setattr(NavPinService, "_is_pinned", staticmethod(never_pinned))
        assert await service.pin(1, "order") is False
        assert await service.list_for(1) == ["order"]

    anyio.run(run)

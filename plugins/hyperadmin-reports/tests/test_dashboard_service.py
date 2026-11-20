"""Unit tests for ``DashboardService`` (#460).

The first ten tests map 1:1 to the scenarios of
``.meta/epics/epicdashboard-dashboard-builder-with-widgets/stories/featdashboard-create-dashboardservice.md``.
The service runs inside real admin requests (``dashboard_support.Mounted.run``), so
``request.state.user`` and ``user_key`` are what the admin's auth sets.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import pytest
from dashboard_support import Mounted, TextWidget, clean_registry, make_engine, mount
from starlette.requests import Request

from hyperadmin_reports import (
    DashboardWidget,
    LayoutStore,
    LayoutUnavailableError,
    register_widget,
)
from hyperadmin_reports.dashboard.layout import LAYOUT_TABLE_NAME
from hyperadmin_reports.dashboard.service import (
    ERROR_TEMPLATE,
    DashboardService,
    LayoutRejectedError,
)

LOGGER = "hyperadmin_reports.dashboard.service"


@pytest.fixture(autouse=True)
def _registered() -> Iterator[None]:
    yield from clean_registry()


def _abc() -> list[TextWidget]:
    return [register_widget(TextWidget(key, permission=f"view_{key}")) for key in ("a", "b", "c")]  # type: ignore[misc]


def _setup(
    tmp_path: Path, *, layouts: bool = True, auth: bool = True, store: bool = True
) -> tuple[Mounted, DashboardService, LayoutStore]:
    engine = make_engine(tmp_path, layouts=layouts)
    mounted = mount(engine, auth=auth)
    layout_store = LayoutStore(engine)
    return mounted, DashboardService(mounted.admin, layout_store if store else None), layout_store


def _keys(widgets: list[DashboardWidget]) -> list[str]:
    return [widget.key for widget in widgets]


def _layout(mounted: Mounted, service: DashboardService, user: str = "alice") -> list[str]:
    async def call(request: Request) -> list[DashboardWidget]:
        return await service.layout_for(request)

    return _keys(mounted.run(call, user=user))


def _save(store: LayoutStore, user_key: Any, keys: list[str]) -> None:
    anyio.run(store.save, user_key, keys)


def _load(store: LayoutStore, user_key: Any) -> list[str] | None:
    return anyio.run(store.load, user_key)


def test_a_saved_order_is_applied(tmp_path: Path) -> None:
    """
    Scenario: a saved order is applied
      Given widgets A, B, C are registered in that order
      And   alice saved [C, A, B]
      When  layout_for(alice_request) is awaited
      Then  the widgets come back as [C, A, B]
    """
    _abc()
    mounted, service, store = _setup(tmp_path)
    _save(store, 1, ["c", "a", "b"])

    assert _layout(mounted, service) == ["c", "a", "b"]


def test_a_user_without_a_saved_order_gets_the_default_order(tmp_path: Path) -> None:
    """
    Scenario: a user without a saved order gets the default order
      Given widgets A, B, C are registered in that order and bob has no row
      When  layout_for(bob_request) is awaited
      Then  the widgets come back as [A, B, C]
    """
    _abc()
    mounted, service, store = _setup(tmp_path)
    _save(store, 1, ["c", "a", "b"])

    assert _layout(mounted, service, user="bob") == ["a", "b", "c"]


def test_widgets_the_user_may_not_view_are_left_out(tmp_path: Path) -> None:
    """
    Scenario: widgets the user may not view are left out
      Given widget P requires view_report_payroll_total
      And   user "viewer" lacks it
      When  layout_for(viewer_request) is awaited
      Then  P is not in the result
    """
    _abc()
    register_widget(TextWidget("p", permission="view_report_payroll_total"))
    mounted, service, _ = _setup(tmp_path)

    assert _layout(mounted, service, user="viewer") == ["a", "b", "c"]
    assert _layout(mounted, service, user="alice") == ["a", "b", "c", "p"]


def test_a_widget_missing_from_the_saved_order_is_appended(tmp_path: Path) -> None:
    """
    Scenario: a widget missing from the saved order is appended
      Given alice saved [B, A] and widgets A, B, C are registered
      When  layout_for(alice_request) is awaited
      Then  the widgets come back as [B, A, C]
    """
    _abc()
    mounted, service, store = _setup(tmp_path)
    _save(store, 1, ["b", "a"])

    assert _layout(mounted, service) == ["b", "a", "c"]


def test_an_unknown_key_in_the_saved_order_is_dropped(tmp_path: Path) -> None:
    """
    Scenario: an unknown key in the saved order is dropped
      Given alice saved [old, A, B] and "old" is not registered
      When  layout_for(alice_request) is awaited
      Then  the widgets come back as [A, B]
    """
    for key in ("a", "b"):
        register_widget(TextWidget(key))
    mounted, service, store = _setup(tmp_path)
    _save(store, 1, ["old", "a", "a", "b"])

    assert _layout(mounted, service) == ["a", "b"]


def test_an_order_that_is_not_a_permutation_of_the_visible_keys_is_rejected(
    tmp_path: Path,
) -> None:
    """
    Scenario: an order that is not a permutation of the visible keys is rejected
      Given alice sees [A, B, C]
      When  save_order(alice_request, ["A", "B", "P"]) is awaited
      Then  LayoutRejectedError is raised
      And   alice's stored order is unchanged
    """
    _abc()
    register_widget(TextWidget("p", permission="view_report_payroll_total"))
    mounted, service, store = _setup(tmp_path)
    _save(store, 3, ["b", "a", "c"])

    async def call(request: Request) -> None:
        for keys in (["a", "b", "p"], ["a", "b"], ["a", "b", "b"], ["a", "b", "c", "x"]):
            with pytest.raises(LayoutRejectedError, match="every visible widget exactly once"):
                await service.save_order(request, keys)
        await service.save_order(request, ["c", "b", "a"])

    assert _load(store, 3) == ["b", "a", "c"]
    mounted.run(call, user="viewer")
    assert _load(store, 3) == ["c", "b", "a"]


def test_move_up_swaps_a_widget_with_its_predecessor(tmp_path: Path) -> None:
    """
    Scenario: move up swaps a widget with its predecessor
      Given alice sees [A, B, C]
      When  move(alice_request, "B", "up") is awaited
      Then  the result and the stored order are [B, A, C]
    """
    _abc()
    mounted, service, store = _setup(tmp_path)

    async def call(request: Request) -> list[list[str]]:
        up = _keys(await service.move(request, "b", "up"))
        down = _keys(await service.move(request, "b", "down"))
        return [up, down]

    assert mounted.run(call) == [["b", "a", "c"], ["a", "b", "c"]]
    assert _load(store, 1) == ["a", "b", "c"]


def test_moving_the_first_widget_up_changes_nothing(tmp_path: Path) -> None:
    """
    Scenario: moving the first widget up changes nothing
      Given alice sees [A, B, C]
      When  move(alice_request, "A", "up") is awaited
      Then  the result is [A, B, C]
    """
    _abc()
    mounted, service, store = _setup(tmp_path)

    async def call(request: Request) -> list[list[str]]:
        first = _keys(await service.move(request, "a", "up"))
        last = _keys(await service.move(request, "c", "down"))
        with pytest.raises(LayoutRejectedError, match="unknown widget 'nope'"):
            await service.move(request, "nope", "up")
        with pytest.raises(LayoutRejectedError, match="unknown direction 'left'"):
            await service.move(request, "a", "left")
        return [first, last]

    assert mounted.run(call) == [["a", "b", "c"], ["a", "b", "c"]]
    assert _load(store, 1) is None


def test_a_failing_widget_renders_an_error_body(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a failing widget renders an error body
      Given a widget whose render() raises RuntimeError
      When  render_body(request, widget) is awaited
      Then  the body template is dashboard/_error.html with the widget key and a retry URL
      And   the error is logged at ERROR with its traceback
    """
    mounted, service, _ = _setup(tmp_path)
    broken = TextWidget("broken", fail=True)
    fine = TextWidget("fine")

    async def call(request: Request) -> list[Any]:
        return [
            await service.render_body(request, broken),
            await service.render_body(request, fine),
        ]

    with caplog.at_level(logging.ERROR, logger=LOGGER):
        error, body = mounted.run(call)

    assert error.template == ERROR_TEMPLATE
    assert error.context["widget"] is broken
    assert error.context["retry_url"].endswith("/widgets/broken")
    assert body.template == "dashboard/_actions.html"
    (record,) = [r for r in caplog.records if r.name == LOGGER]
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "dashboard widget 'broken' failed to render"
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], RuntimeError)


def test_a_missing_layout_table_turns_persistence_off_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a missing layout table turns persistence off once
      Given the layout table does not exist
      When  layout_for is awaited twice
      Then  both calls return the default order
      And   can_persist is False
      And   one warning naming hyperadmin_reports_dashboard_layout is logged
    """
    _abc()
    mounted, service, _ = _setup(tmp_path, layouts=False)
    assert service.can_persist is True

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        # Two requests find the table missing at the same moment: still one warning.
        async def both(request: Request) -> list[list[DashboardWidget]]:
            return await asyncio.gather(service.layout_for(request), service.layout_for(request))

        first, second = (_keys(widgets) for widgets in mounted.run(both))
        assert _layout(mounted, service) == first

        async def call(request: Request) -> bool:
            with pytest.raises(LayoutUnavailableError):
                await service.save_order(request, ["a", "b", "c"])
            with pytest.raises(LayoutUnavailableError):
                await service.move(request, "b", "up")
            await service.reset(request)
            return service.can_persist_for(request)

        can_persist_for = mounted.run(call)

    assert first == second == ["a", "b", "c"]
    assert service.can_persist is False
    assert can_persist_for is False
    (record,) = [r for r in caplog.records if r.name == LOGGER]
    assert record.levelno == logging.WARNING
    assert LAYOUT_TABLE_NAME in record.getMessage()


def test_reset_forgets_the_saved_order(tmp_path: Path) -> None:
    """
    Scenario: reset returns to the default order
      Given alice saved [C, A, B]
      When  reset(alice_request) is awaited twice
      Then  alice sees [A, B, C] and has no saved layout row
    """
    _abc()
    mounted, service, store = _setup(tmp_path)
    _save(store, 1, ["c", "a", "b"])

    async def call(request: Request) -> bool:
        await service.reset(request)
        await service.reset(request)
        return service.can_persist_for(request)

    assert mounted.run(call) is True
    assert _load(store, 1) is None
    assert _layout(mounted, service) == ["a", "b", "c"]


@pytest.mark.parametrize("method", ["save_order", "move", "reset"])
def test_a_missing_table_found_by_a_write_turns_persistence_off(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, method: str
) -> None:
    """
    Scenario: a write that finds the layout table missing turns persistence off
      Given the layout table does not exist and nothing was loaded yet
      When  alice saves an order, moves a widget or resets
      Then  the save and the move raise LayoutUnavailableError and the reset does nothing
      And   can_persist is False and one warning is logged
    """
    _abc()
    mounted, service, _ = _setup(tmp_path, layouts=False)

    async def call(request: Request) -> None:
        if method == "reset":
            await service.reset(request)
        elif method == "move":
            with pytest.raises(LayoutUnavailableError):
                await service.move(request, "b", "up")
        else:
            with pytest.raises(LayoutUnavailableError):
                await service.save_order(request, ["c", "b", "a"])

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        mounted.run(call)
        mounted.run(call)

    assert service.can_persist is False
    assert len([r for r in caplog.records if r.name == LOGGER]) == 1


def test_without_a_store_nothing_is_persisted_and_nothing_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: dashboard_layouts=False means no table access and no warning
      Given a service built with store=None and a database without the layout table
      When  alice asks for her layout, saves an order and resets
      Then  she gets the default order, the save raises LayoutUnavailableError
      And   nothing is logged
    """
    _abc()
    mounted, service, _ = _setup(tmp_path, layouts=False, store=False)

    async def call(request: Request) -> list[str]:
        with pytest.raises(LayoutUnavailableError):
            await service.save_order(request, ["c", "b", "a"])
        await service.reset(request)
        assert service.can_persist_for(request) is False
        return _keys(await service.layout_for(request))

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert mounted.run(call) == ["a", "b", "c"]

    assert service.can_persist is False
    assert [r for r in caplog.records if r.name == LOGGER] == []


def test_without_auth_every_widget_is_visible_and_writes_are_refused(tmp_path: Path) -> None:
    """
    Scenario: no auth means every widget is visible and nothing can be saved
      Given the admin has no authentication configured
      When  a request asks for the layout and then tries to save, move and reset
      Then  every registered widget is returned in the default order
      And   the write methods raise PermissionError
    """
    _abc()
    register_widget(TextWidget("p", permission="view_report_payroll_total"))
    mounted, service, store = _setup(tmp_path, auth=False)

    async def call(request: Request) -> list[str]:
        assert service.can_persist_for(request) is False
        with pytest.raises(PermissionError):
            await service.save_order(request, ["a", "b", "c", "p"])
        with pytest.raises(PermissionError):
            await service.move(request, "b", "up")
        with pytest.raises(PermissionError):
            await service.reset(request)
        return _keys(await service.layout_for(request))

    assert mounted.run(call) == ["a", "b", "c", "p"]
    assert service.can_persist is True
    assert _load(store, 1) is None

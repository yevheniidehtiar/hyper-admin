"""The dashboard's rules: who sees which widget, in which order, and what may be saved.

The routes parse input and pick templates; everything else lives here, so the
same rules hold for the page, the widget fragments and the layout POSTs:

* a widget is visible only to users holding its codename; a hidden widget is
  never rendered, loaded or accepted in a saved order;
* the order is the user's saved order (unknown and hidden keys dropped), then
  the widgets it does not name, in registration order;
* a saved order must be a permutation of the widgets the user sees;
* a widget whose ``render()`` raises becomes an error body, logged with its key;
* without the layout table the dashboard keeps the default order: the first
  failure is logged once per admin and persistence stays off.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hyperadmin.views.urls import admin_url_for
from hyperadmin_reports.admin_context import has_permission
from hyperadmin_reports.dashboard.layout import LAYOUT_TABLE_NAME, LayoutUnavailableError
from hyperadmin_reports.dashboard.widgets import WidgetBody, registered_widgets

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request

    from hyperadmin_reports.dashboard.layout import LayoutStore
    from hyperadmin_reports.dashboard.widgets import DashboardWidget

logger = logging.getLogger(__name__)

#: Body of a widget whose ``render()`` raised.
ERROR_TEMPLATE = "dashboard/_error.html"
#: Directions ``move`` accepts.
DIRECTIONS = ("up", "down")


class LayoutRejectedError(ValueError):
    """The submitted order (or move) does not fit the widgets the user sees."""


class DashboardService:
    """Visibility, order, saving and failure isolation for one admin's dashboard.

    ``store`` is ``None`` when layouts are switched off (``dashboard_layouts=False``):
    the default order is served and the layout table is never touched.
    """

    def __init__(self, admin: Any, store: LayoutStore | None) -> None:
        self.admin = admin
        self.store = store
        self._available = store is not None

    @property
    def can_persist(self) -> bool:
        """Whether orders can be saved at all: a store is set and its table is usable."""
        return self._available

    def can_persist_for(self, request: Request) -> bool:
        """Whether this request may reorder: persistence is on and it has a ``user_key``."""
        return self._available and _user_key(request) is not None

    async def visible(self, request: Request) -> list[DashboardWidget]:
        """Registered widgets the request's user may view, in registration order."""
        return [
            widget
            for widget in registered_widgets()
            if await has_permission(self.admin, request, widget.permission())
        ]

    async def layout_for(self, request: Request) -> list[DashboardWidget]:
        """The visible widgets in the user's order (saved order first, then the rest)."""
        widgets = await self.visible(request)
        saved = await self._saved(request)
        if not saved:
            return widgets
        by_key = {widget.key: widget for widget in widgets}
        ordered = [by_key.pop(key) for key in dict.fromkeys(saved) if key in by_key]
        return [*ordered, *by_key.values()]

    async def save_order(self, request: Request, keys: Sequence[str]) -> None:
        """Store ``keys`` as the user's order.

        Raises:
            PermissionError: The request has no ``user_key`` (no signed-in user).
            LayoutRejectedError: ``keys`` is not a permutation of the visible widget keys.
            LayoutUnavailableError: Layouts are off or the layout table is not usable.
        """
        user_key = self._writer(request)
        visible = [widget.key for widget in await self.visible(request)]
        if len(keys) != len(visible) or set(keys) != set(visible):
            raise LayoutRejectedError("the order must list every visible widget exactly once")
        await self._save(user_key, list(keys))

    async def move(self, request: Request, key: str, direction: str) -> list[DashboardWidget]:
        """Swap widget ``key`` with its neighbour and return the new order.

        Moving the first widget up or the last one down changes nothing.

        Raises:
            PermissionError: The request has no ``user_key``.
            LayoutRejectedError: Unknown (or hidden) ``key``, or a direction other than up / down.
            LayoutUnavailableError: Layouts are off or the layout table is not usable.
        """
        user_key = self._writer(request)
        if direction not in DIRECTIONS:
            raise LayoutRejectedError(f"unknown direction {direction!r}")
        widgets = await self.layout_for(request)
        if not self._available:
            raise LayoutUnavailableError
        index = next((i for i, widget in enumerate(widgets) if widget.key == key), None)
        if index is None:
            raise LayoutRejectedError(f"unknown widget {key!r}")
        target = index - 1 if direction == "up" else index + 1
        if not 0 <= target < len(widgets):
            return widgets
        widgets[index], widgets[target] = widgets[target], widgets[index]
        await self._save(user_key, [widget.key for widget in widgets])
        return widgets

    async def reset(self, request: Request) -> None:
        """Forget the user's saved order (a no-op without one, or without persistence).

        Raises:
            PermissionError: The request has no ``user_key``.
        """
        user_key = self._writer(request)
        if self.store is None or not self._available:
            return
        try:
            await self.store.reset(user_key)
        except LayoutUnavailableError as exc:
            self._turn_off(exc)

    async def render_body(self, request: Request, widget: DashboardWidget) -> WidgetBody:
        """``widget.render()``, or the error body (with a retry URL) when it raises."""
        try:
            return await widget.render(request, self.admin)
        except Exception:
            logger.exception("dashboard widget %r failed to render", widget.key)
            retry_url = admin_url_for(request, "dashboard-widget", key=widget.key).path
            return WidgetBody(ERROR_TEMPLATE, {"widget": widget, "retry_url": retry_url})

    # -- internals ----------------------------------------------------------------

    @staticmethod
    def _writer(request: Request) -> Any:
        user_key = _user_key(request)
        if user_key is None:
            raise PermissionError("saving a dashboard layout needs a signed-in user")
        return user_key

    async def _saved(self, request: Request) -> list[str] | None:
        user_key = _user_key(request)
        if self.store is None or not self._available or user_key is None:
            return None
        try:
            return await self.store.load(user_key)
        except LayoutUnavailableError as exc:
            self._turn_off(exc)
            return None

    async def _save(self, user_key: Any, keys: list[str]) -> None:
        if self.store is None or not self._available:
            raise LayoutUnavailableError
        try:
            await self.store.save(user_key, keys)
        except LayoutUnavailableError as exc:
            self._turn_off(exc)
            raise

    def _turn_off(self, error: LayoutUnavailableError) -> None:
        """Stop using the layout table for this admin and say so once."""
        if not self._available:  # a concurrent request already reported it
            return
        self._available = False
        logger.warning(
            "dashboard layouts are off: the %s table is not available. Create it with "
            "hyperadmin_reports.create_layout_table() or set dashboard_layouts=False.",
            LAYOUT_TABLE_NAME,
            exc_info=error,
        )


def _user_key(request: Request) -> Any:
    return getattr(request.state, "user_key", None)

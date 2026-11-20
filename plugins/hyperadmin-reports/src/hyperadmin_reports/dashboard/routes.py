"""The dashboard page: the grid, the widget fragments and the layout POSTs.

:func:`build_dashboard_router` returns a plain ``APIRouter`` the plugin hands
to ``admin.plugins.add_page`` under ``ReportsSettings.dashboard_prefix``, so the
routes run inside the admin sub-app with its session, user, CSRF guard and
error pages. :func:`index_endpoint` is the same page as an
``async (request) -> Response`` callable, which the plugin gives to
``admin.plugins.set_home_page`` to serve it at the admin index.

The routes parse input, call :class:`~hyperadmin_reports.dashboard.service.DashboardService`
and pick a template. Every POST answers an HTMX request with a fragment (or
204) and a plain form post with a 303 back to the dashboard, so reordering
works without JavaScript.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.routing import APIRoute
from markupsafe import Markup
from starlette.responses import Response

from hyperadmin.views.urls import admin_url_for
from hyperadmin_reports.admin_context import has_permission
from hyperadmin_reports.dashboard.layout import LayoutStore, LayoutUnavailableError
from hyperadmin_reports.dashboard.service import DashboardService, LayoutRejectedError
from hyperadmin_reports.dashboard.widgets import get_widget

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from hyperadmin_reports.dashboard.widgets import DashboardWidget
    from hyperadmin_reports.settings import ReportsSettings

#: ``id`` of the grid element; the HTMX target of the move and reset forms.
GRID_ID = "dashboard-grid"
#: Route name of the dashboard page.
INDEX_ROUTE = "dashboard-index"


def index_endpoint(router: APIRouter) -> Callable[[Request], Awaitable[Response]]:
    """The dashboard page handler of ``router``, for ``PluginRegistry.set_home_page``."""
    return next(
        route.endpoint
        for route in router.routes
        if isinstance(route, APIRoute) and route.name == INDEX_ROUTE
    )


def build_dashboard_router(admin: Any, settings: ReportsSettings) -> APIRouter:  # noqa: PLR0915 - one closure per route
    """The dashboard router; ``admin`` is read per request, so it may be half-built here."""
    router = APIRouter()
    state: dict[str, DashboardService] = {}

    def service() -> DashboardService:
        """The admin's service, built on the first request (the admin is complete by then)."""
        if "service" not in state:
            store = (
                LayoutStore(admin.engine, session_factory=admin.session_factory)
                if settings.dashboard_layouts
                else None
            )
            state["service"] = DashboardService(admin, store)
        return state["service"]

    def is_htmx(request: Request) -> bool:
        return bool(request.headers.get("hx-request"))

    def url(request: Request, name: str, **params: Any) -> str:
        return admin_url_for(request, name, **params).path

    def render(request: Request, template: str, context: dict[str, Any], status: int = 200) -> Any:
        return admin.templates.TemplateResponse(request, template, context, status_code=status)

    async def card(request: Request, widget: DashboardWidget) -> dict[str, Any]:
        """One card of the grid; a widget that is not lazy is rendered with the page."""
        body = None
        if not widget.lazy:
            rendered = await service().render_body(request, widget)
            body = Markup(render(request, rendered.template, rendered.context).body.decode())  # noqa: S704 - autoescaped template output
        return {
            "widget": widget,
            "body": body,
            "fragment_url": widget.fragment_url(request) if widget.lazy else None,
            "detail_url": widget.detail_url(request),
        }

    async def grid_context(
        request: Request, widgets: list[DashboardWidget], moved: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "cards": [await card(request, widget) for widget in widgets],
            # Read after the layout was loaded: a missing table has turned it off by now.
            "can_reorder": service().can_persist_for(request),
            "grid_id": GRID_ID,
            "layout_url": url(request, "dashboard-layout"),
            "move_url": url(request, "dashboard-layout-move"),
            "reset_url": url(request, "dashboard-reset"),
            "moved": moved,
        }

    async def guarded(action: Awaitable[Any]) -> Any:
        """Await a service write, mapping its refusals to 403 / 400 / 503."""
        try:
            return await action
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LayoutRejectedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LayoutUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="Dashboard layouts are not available"
            ) from exc

    def back(request: Request) -> Response:
        return RedirectResponse(url(request, INDEX_ROUTE), status_code=303)

    @router.get("/", name=INDEX_ROUTE, response_class=HTMLResponse)
    async def dashboard_index(request: Request) -> Response:
        widgets = await service().layout_for(request)
        targets_grid = is_htmx(request) and request.headers.get("hx-target") == GRID_ID
        template = "dashboard/_grid.html" if targets_grid else "dashboard/index.html"
        return render(request, template, await grid_context(request, widgets))

    @router.get("/widgets/{key}", name="dashboard-widget", response_class=HTMLResponse)
    async def dashboard_widget(request: Request, key: str) -> Response:
        widget = get_widget(key)
        if widget is None:
            raise HTTPException(status_code=404, detail="Widget not found")
        if not await has_permission(admin, request, widget.permission()):
            return render(request, "dashboard/_forbidden.html", {"widget": widget}, status=403)
        body = await service().render_body(request, widget)
        return render(request, body.template, body.context)

    @router.post("/layout", name="dashboard-layout")
    async def dashboard_layout(request: Request) -> Response:
        form = await request.form()
        keys = [str(value) for value in form.getlist("widgets")]
        await guarded(service().save_order(request, keys))
        return Response(status_code=204) if is_htmx(request) else back(request)

    @router.post("/layout/move", name="dashboard-layout-move")
    async def dashboard_layout_move(request: Request) -> Response:
        form = await request.form()
        key, direction = str(form.get("key", "")), str(form.get("direction", ""))
        widgets = await guarded(service().move(request, key, direction))
        if not is_htmx(request):
            return back(request)
        position = next(i for i, widget in enumerate(widgets, start=1) if widget.key == key)
        moved = {
            "key": key,
            "direction": direction,
            "title": widgets[position - 1].title,
            "position": position,
            "total": len(widgets),
        }
        return render(request, "dashboard/_grid.html", await grid_context(request, widgets, moved))

    @router.post("/reset", name="dashboard-reset")
    async def dashboard_reset(request: Request) -> Response:
        await guarded(service().reset(request))
        if not is_htmx(request):
            return back(request)
        widgets = await service().layout_for(request)
        return render(request, "dashboard/_grid.html", await grid_context(request, widgets))

    return router

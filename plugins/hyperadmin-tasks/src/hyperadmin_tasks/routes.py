"""Admin pages of the tasks plugin.

:func:`build_router` returns a plain ``APIRouter`` the plugin hands to
``admin.plugins.add_page``; ``Admin.mount()`` rebuilds it on the admin's route class under
``{prefix}/tasks``. Pages are gated on ``view_tasks`` through the same permission checker the
admin hands to its model views; a user who lacks it gets the plugin's own 403 card. Without
auth every page is open, as model views are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response  # noqa: TC002 - FastAPI resolves the return annotation

if TYPE_CHECKING:
    from hyperadmin_tasks.lifecycle import BackendLifecycle

#: Permission to see the task pages.
VIEW_PERMISSION = "view_tasks"


def _permission_checker(admin: Any) -> Any:
    """The checker admin model views use: none unless the admin has auth configured."""
    if getattr(admin, "auth", None) is None and getattr(admin, "auth_backend", None) is None:
        return None
    return admin.permission_checker


async def can_view(admin: Any, request: Request) -> bool:
    """Whether the request's user holds ``view_tasks``."""
    checker = _permission_checker(admin)
    if checker is None:
        return True
    user = getattr(request.state, "user", None)
    return user is not None and bool(await checker.has_permission(user, VIEW_PERMISSION))


def build_router(admin: Any, lifecycle: BackendLifecycle) -> APIRouter:
    """The tasks page router; ``admin`` is read per request, so it may be half-built here.

    Pages start the backend on first use through ``lifecycle``.
    """
    router = APIRouter()

    @router.get("/", name="tasks-dashboard", response_class=HTMLResponse)
    async def tasks_dashboard(request: Request) -> Response:
        if not await can_view(admin, request):
            return admin.templates.TemplateResponse(
                request,
                "tasks/forbidden.html",
                {"codename": VIEW_PERMISSION, "permission_name": "Can view tasks"},
                status_code=403,
            )
        await lifecycle.ensure_started()
        return admin.templates.TemplateResponse(request, "tasks/dashboard.html", {})

    return router

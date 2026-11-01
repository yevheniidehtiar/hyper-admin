"""Admin pages of the tasks plugin.

:func:`build_router` returns a plain ``APIRouter`` the plugin hands to
``admin.plugins.add_page``; ``Admin.mount()`` rebuilds it on the admin's route class under
``{prefix}/tasks``. Pages are gated on ``view_tasks`` through the same permission checker the
admin hands to its model views; a user who lacks it gets the plugin's own 403 card. Without
auth every page is open, as model views are.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response  # noqa: TC002 - FastAPI resolves the return annotation

from hyperadmin_tasks.backend import Capability, QueueStats
from hyperadmin_tasks.presenters import format_age
from hyperadmin_tasks.settings import TasksSettings

if TYPE_CHECKING:
    from hyperadmin_tasks.lifecycle import BackendLifecycle

logger = logging.getLogger(__name__)

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


async def _load_overview(lifecycle: BackendLifecycle) -> dict[str, Any]:
    """Queue stats and the active-worker count; a failing backend yields ``error`` instead."""
    try:
        backend = await lifecycle.ensure_started()
        queues = await backend.list_queues()
        workers = (
            sum(w.healthy for w in await backend.list_workers())
            if Capability.WORKERS in backend.capabilities
            else None
        )
    except Exception:  # the backend is third-party; any failure becomes the inline banner
        logger.warning("tasks backend failed while loading the dashboard", exc_info=True)
        return {"queues": [], "workers": None, "error": True}
    return {"queues": [_queue_row(queue) for queue in queues], "workers": workers, "error": False}


def _queue_row(queue: QueueStats) -> dict[str, Any]:
    return {"stats": queue, "oldest_ready": format_age(queue.oldest_ready_age)}


def build_router(
    admin: Any, lifecycle: BackendLifecycle, settings: TasksSettings | None = None
) -> APIRouter:
    """The tasks page router; ``admin`` is read per request, so it may be half-built here.

    Pages start the backend on first use through ``lifecycle``; ``settings`` supplies the
    dashboard refresh interval.
    """
    router = APIRouter()
    config = settings or TasksSettings()

    async def forbidden(request: Request) -> Response:
        return admin.templates.TemplateResponse(
            request,
            "tasks/forbidden.html",
            {"codename": VIEW_PERMISSION, "permission_name": "Can view tasks"},
            status_code=403,
        )

    @router.get("/", name="tasks-dashboard", response_class=HTMLResponse)
    async def tasks_dashboard(request: Request) -> Response:
        if not await can_view(admin, request):
            return await forbidden(request)
        context = await _load_overview(lifecycle)
        context["refresh_seconds"] = config.refresh_seconds
        template = (
            "tasks/_queue_stats.html"
            if request.query_params.get("partial") == "1"
            else "tasks/dashboard.html"
        )
        return admin.templates.TemplateResponse(request, template, context)

    return router

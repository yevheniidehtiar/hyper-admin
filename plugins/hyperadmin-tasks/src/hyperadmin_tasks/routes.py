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

from hyperadmin_tasks.backend import (
    AttemptRecord,
    Capability,
    QueueStats,
    ScheduleRecord,
    TaskFilter,
    TaskRecord,
    TaskState,
    WorkerRecord,
)
from hyperadmin_tasks.presenters import (
    STATE_PILL_KIND,
    Pagination,
    format_age,
    format_utc,
    list_url,
    render_json,
)
from hyperadmin_tasks.settings import TasksSettings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from hyperadmin_tasks.backend import TaskBackend
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


def _parse_page(raw: str) -> int:
    """The 1-based page number in ``raw``; anything that is not a positive integer is page 1."""
    return int(raw) if raw.isdecimal() and int(raw) > 0 else 1


def _parse_state(raw: str) -> TaskState | None:
    """The task state named by ``raw``, or ``None`` when it names none (filter is ignored)."""
    try:
        return TaskState(raw)
    except ValueError:
        return None


def _queue_row(queue: QueueStats) -> dict[str, Any]:
    return {"stats": queue, "oldest_ready": format_age(queue.oldest_ready_age)}


def _worker_rows(workers: list[WorkerRecord]) -> list[dict[str, Any]]:
    return [{"worker": w, "last_seen": format_utc(w.last_seen_at)} for w in workers]


def _schedule_rows(schedules: list[ScheduleRecord]) -> list[dict[str, Any]]:
    return [{"schedule": s, "next_run": format_utc(s.next_run_at)} for s in schedules]


def _detail_context(task: TaskRecord, attempts: list[AttemptRecord], full: str) -> dict[str, Any]:
    """Template context of the detail page; ``full`` names the JSON block to show untruncated."""
    return {
        "task": task,
        "attempts": [
            {
                "attempt": attempt,
                "started": format_utc(attempt.started_at),
                "finished": format_utc(attempt.finished_at),
            }
            for attempt in attempts
        ],
        "pill_kind": STATE_PILL_KIND[task.state],
        "payload": render_json(task.payload, full=full == "payload"),
        "result": render_json(task.result, full=full == "result"),
        "created": format_utc(task.created_at),
        "run_at": format_utc(task.run_at),
        "finished": format_utc(task.finished_at),
        "error": False,
    }


async def _forbidden(admin: Any, request: Request) -> Response:
    return admin.templates.TemplateResponse(
        request,
        "tasks/forbidden.html",
        {"codename": VIEW_PERMISSION, "permission_name": "Can view tasks"},
        status_code=403,
    )


async def _not_found(admin: Any, request: Request, heading: str, text: str) -> Response:
    return admin.templates.TemplateResponse(
        request, "tasks/not_found.html", {"heading": heading, "text": text}, status_code=404
    )


def _add_inventory_routes(router: APIRouter, admin: Any, lifecycle: BackendLifecycle) -> None:
    """Add the workers, schedules and task detail pages to ``router``."""

    async def inventory(
        request: Request,
        capability: Capability,
        noun: str,
        load: Callable[[TaskBackend], Awaitable[list[Any]]],
        rows: Callable[[list[Any]], list[dict[str, Any]]],
    ) -> Response:
        if not await can_view(admin, request):
            return await _forbidden(admin, request)
        template = f"tasks/{noun}.html"
        try:
            backend = await lifecycle.ensure_started()
            if capability not in backend.capabilities:
                return await _not_found(
                    admin,
                    request,
                    f"{noun.capitalize()} are not available",
                    f"This backend does not report {noun}.",
                )
            context: dict[str, Any] = {"rows": rows(await load(backend)), "error": False}
        except Exception:  # the backend is third-party; any failure becomes the inline banner
            logger.warning("tasks backend failed while listing %s", noun, exc_info=True)
            context = {"rows": [], "error": True}
        return admin.templates.TemplateResponse(request, template, context)

    @router.get("/workers", name="tasks-workers", response_class=HTMLResponse)
    async def tasks_workers(request: Request) -> Response:
        return await inventory(
            request, Capability.WORKERS, "workers", lambda b: b.list_workers(), _worker_rows
        )

    @router.get("/schedules", name="tasks-schedules", response_class=HTMLResponse)
    async def tasks_schedules(request: Request) -> Response:
        return await inventory(
            request, Capability.SCHEDULES, "schedules", lambda b: b.list_schedules(), _schedule_rows
        )

    @router.get("/t/{task_id}", name="tasks-detail", response_class=HTMLResponse)
    async def tasks_detail(request: Request, task_id: str, full: str = "") -> Response:
        if not await can_view(admin, request):
            return await _forbidden(admin, request)
        try:
            found = await (await lifecycle.ensure_started()).get_task(task_id)
        except Exception:  # the backend is third-party; any failure becomes the inline banner
            logger.warning("tasks backend failed while loading a task", exc_info=True)
            return admin.templates.TemplateResponse(
                request, "tasks/task_detail.html", {"task": None, "error": True}
            )
        if found is None:
            return await _not_found(
                admin, request, "Task not found", "It never existed, or retention has removed it."
            )
        context = _detail_context(*found, full)
        return admin.templates.TemplateResponse(request, "tasks/task_detail.html", context)


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
        return await _forbidden(admin, request)

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

    @router.get("/list", name="tasks-list", response_class=HTMLResponse)
    async def tasks_list(
        request: Request,
        queue: str = "",
        state: str = "",
        name: str = "",
        q: str = "",
        page: str = "1",
    ) -> Response:
        if not await can_view(admin, request):
            return await forbidden(request)
        state_filter = _parse_state(state)
        filters = {
            "queue": queue,
            "state": state_filter.value if state_filter else "",
            "name": name,
            "q": q,
        }
        number = _parse_page(page)
        context: dict[str, Any] = {
            "filters": filters,
            "states": list(TaskState),
            "queues": [],
            "rows": [],
            "pagination": None,
            "prev_url": None,
            "next_url": None,
            "error": False,
        }
        try:
            backend = await lifecycle.ensure_started()
            queue_names = [stats.name for stats in await backend.list_queues()]
            result = await backend.list_tasks(
                TaskFilter(
                    queue=queue or None,
                    state=state_filter,
                    name=name or None,
                    id_query=q or None,
                ),
                number,
                config.page_size,
            )
        except Exception:  # the backend is third-party; any failure becomes the inline banner
            logger.warning("tasks backend failed while listing tasks", exc_info=True)
            context["error"] = True
            return admin.templates.TemplateResponse(request, "tasks/task_list.html", context)
        pagination = Pagination(result.page, result.per_page, len(result.items), result.total)
        base = request.url.path
        context.update(
            queues=queue_names,
            rows=[{"task": task, "pill": STATE_PILL_KIND[task.state]} for task in result.items],
            pagination=pagination,
            prev_url=list_url(base, filters, number - 1) if pagination.has_previous else None,
            next_url=list_url(base, filters, number + 1) if pagination.has_next else None,
        )
        return admin.templates.TemplateResponse(request, "tasks/task_list.html", context)

    _add_inventory_routes(router, admin, lifecycle)

    return router

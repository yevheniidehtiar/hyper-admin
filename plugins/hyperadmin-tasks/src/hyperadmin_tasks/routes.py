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
from starlette.responses import RedirectResponse, Response

from hyperadmin.views.urls import admin_url_for
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
    CANCELLABLE_STATES,
    RETRYABLE_STATES,
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
#: Permission to act on tasks, queues and schedules.
MANAGE_PERMISSION = "manage_tasks"


def _permission_checker(admin: Any) -> Any:
    """The checker admin model views use: none unless the admin has auth configured."""
    if getattr(admin, "auth", None) is None and getattr(admin, "auth_backend", None) is None:
        return None
    return admin.permission_checker


async def _has_permission(admin: Any, request: Request, codename: str) -> bool:
    checker = _permission_checker(admin)
    if checker is None:
        return True
    user = getattr(request.state, "user", None)
    return user is not None and bool(await checker.has_permission(user, codename))


async def can_view(admin: Any, request: Request) -> bool:
    """Whether the request's user holds ``view_tasks``."""
    return await _has_permission(admin, request, VIEW_PERMISSION)


async def can_manage(admin: Any, request: Request) -> bool:
    """Whether the request's user holds ``manage_tasks``."""
    return await _has_permission(admin, request, MANAGE_PERMISSION)


def _actor(request: Request) -> str:
    """The name the backend records for an action: the signed-in user's display name."""
    return str(getattr(request.state, "user_display", "") or "anonymous")


def _action_flags(manage: bool, backend: TaskBackend) -> dict[str, bool]:
    """Which action controls to render: the user may manage and the backend can do it."""
    return {
        "retry": manage and Capability.RETRY in backend.capabilities,
        "cancel": manage and Capability.CANCEL in backend.capabilities,
        "pause_queue": manage and Capability.PAUSE_QUEUE in backend.capabilities,
        "pause_schedule": manage and Capability.PAUSE_SCHEDULE in backend.capabilities,
    }


async def _load_overview(lifecycle: BackendLifecycle, manage: bool = False) -> dict[str, Any]:
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
        return {"queues": [], "workers": None, "can": {}, "error": True}
    return {
        "queues": [_queue_row(queue) for queue in queues],
        "workers": workers,
        "can": _action_flags(manage, backend),
        "error": False,
    }


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


def _detail_context(
    task: TaskRecord, attempts: list[AttemptRecord], full: str, can: dict[str, bool]
) -> dict[str, Any]:
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
        "can": {
            "retry": can["retry"] and task.state in RETRYABLE_STATES,
            "cancel": can["cancel"] and task.state in CANCELLABLE_STATES,
        },
        "error": False,
    }


async def _forbidden(
    admin: Any,
    request: Request,
    codename: str = VIEW_PERMISSION,
    permission_name: str = "Can view tasks",
) -> Response:
    return admin.templates.TemplateResponse(
        request,
        "tasks/forbidden.html",
        {"codename": codename, "permission_name": permission_name},
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
            context: dict[str, Any] = {
                "rows": rows(await load(backend)),
                "can": _action_flags(await can_manage(admin, request), backend),
                "error": False,
            }
        except Exception:  # the backend is third-party; any failure becomes the inline banner
            logger.warning("tasks backend failed while listing %s", noun, exc_info=True)
            context = {"rows": [], "can": {}, "error": True}
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
            backend = await lifecycle.ensure_started()
            found = await backend.get_task(task_id)
        except Exception:  # the backend is third-party; any failure becomes the inline banner
            logger.warning("tasks backend failed while loading a task", exc_info=True)
            return admin.templates.TemplateResponse(
                request, "tasks/task_detail.html", {"task": None, "error": True}
            )
        if found is None:
            return await _not_found(
                admin, request, "Task not found", "It never existed, or retention has removed it."
            )
        can = _action_flags(await can_manage(admin, request), backend)
        context = _detail_context(*found, full, can)
        return admin.templates.TemplateResponse(request, "tasks/task_detail.html", context)


def _add_action_routes(router: APIRouter, admin: Any, lifecycle: BackendLifecycle) -> None:
    """Add the POST-only retry / cancel / pause / resume routes to ``router``.

    The admin's route class enforces CSRF before a handler runs. Each action answers with a 303
    to the page it was started from, carrying a ``notice`` code the page renders as a flash.
    """

    async def perform(
        request: Request,
        run: Callable[[TaskBackend, str], Awaitable[None]],
        page: str,
        ok_notice: str,
        **page_params: str,
    ) -> Response:
        if not await can_manage(admin, request):
            return await _forbidden(admin, request, MANAGE_PERMISSION, "Can manage tasks")
        try:
            await run(await lifecycle.ensure_started(), _actor(request))
            notice = ok_notice
        except Exception:  # the backend is third-party; any failure becomes the error flash
            logger.warning("tasks backend action failed", exc_info=True)
            notice = "failed"
        target = admin_url_for(request, page, **page_params).include_query_params(notice=notice)
        return RedirectResponse(f"{target.path}?{target.query}", status_code=303)

    @router.post("/t/{task_id}/retry", name="tasks-retry")
    async def tasks_retry(request: Request, task_id: str) -> Response:
        return await perform(
            request,
            lambda b, actor: b.retry_task(task_id, actor=actor),
            "tasks-detail",
            "retried",
            task_id=task_id,
        )

    @router.post("/t/{task_id}/cancel", name="tasks-cancel")
    async def tasks_cancel(request: Request, task_id: str) -> Response:
        return await perform(
            request,
            lambda b, actor: b.cancel_task(task_id, actor=actor),
            "tasks-detail",
            "cancelled",
            task_id=task_id,
        )

    @router.post("/queues/{name}/pause", name="tasks-queue-pause")
    async def tasks_queue_pause(request: Request, name: str) -> Response:
        return await perform(
            request,
            lambda b, actor: b.set_queue_paused(name, True, actor=actor),
            "tasks-dashboard",
            "queue-paused",
        )

    @router.post("/queues/{name}/resume", name="tasks-queue-resume")
    async def tasks_queue_resume(request: Request, name: str) -> Response:
        return await perform(
            request,
            lambda b, actor: b.set_queue_paused(name, False, actor=actor),
            "tasks-dashboard",
            "queue-resumed",
        )

    @router.post("/schedules/{schedule_id}/pause", name="tasks-schedule-pause")
    async def tasks_schedule_pause(request: Request, schedule_id: str) -> Response:
        return await perform(
            request,
            lambda b, actor: b.set_schedule_paused(schedule_id, True, actor=actor),
            "tasks-schedules",
            "schedule-paused",
        )

    @router.post("/schedules/{schedule_id}/resume", name="tasks-schedule-resume")
    async def tasks_schedule_resume(request: Request, schedule_id: str) -> Response:
        return await perform(
            request,
            lambda b, actor: b.set_schedule_paused(schedule_id, False, actor=actor),
            "tasks-schedules",
            "schedule-resumed",
        )


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
        context = await _load_overview(lifecycle, await can_manage(admin, request))
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
    _add_action_routes(router, admin, lifecycle)

    return router

"""Admin pages for registered reports: an index, the HTML grid and CSV / XLSX exports.

:func:`build_router` returns a plain ``APIRouter`` the plugin hands to
``admin.plugins.add_page``; ``Admin.mount()`` rebuilds it on the admin's
``HyperAdminRoute`` under ``{prefix}/reports``, so the routes run inside the
admin sub-app with its session, user, CSRF guard and error pages. Route names
join the ``hyperadmin:`` namespace (``hyperadmin:report-detail``, ...).

Every report route checks the report's codename (default ``view_report_{slug}``)
through the same permission checker the admin hands to its model views: the
built-in ``ModelPermissionChecker``, or the bridge checker with ``auth=``.
Without auth every report is open, as model views are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.ext.asyncio import async_sessionmaker

from hyperadmin_reports.export import XLSX_MEDIA_TYPE, build_table, stream_csv, stream_xlsx
from hyperadmin_reports.view import get_report, registered_reports

if TYPE_CHECKING:
    from starlette.responses import Response

    from hyperadmin_reports.export import ReportTable
    from hyperadmin_reports.view import ReportView, SessionSource


def _permission_checker(admin: Any) -> Any:
    """The checker admin model views use: none unless the admin has auth configured."""
    if getattr(admin, "auth", None) is None and getattr(admin, "auth_backend", None) is None:
        return None
    return admin.permission_checker


async def can_view(admin: Any, request: Request, report: type[ReportView]) -> bool:
    """Whether the request's user holds ``report``'s permission codename."""
    checker = _permission_checker(admin)
    if checker is None:
        return True
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=403, detail="Authentication required")
    return bool(await checker.has_permission(user, report.get_permission()))


def _session_source(admin: Any) -> SessionSource:
    if admin.session_factory is not None:
        return admin.session_factory
    return async_sessionmaker(admin.engine, expire_on_commit=False)


def build_router(admin: Any) -> APIRouter:
    """The reports page router; ``admin`` is read per request, so it may be half-built here."""
    router = APIRouter()

    async def authorized(request: Request, slug: str) -> type[ReportView]:
        report = get_report(slug)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        if not await can_view(admin, request, report):
            raise HTTPException(status_code=403, detail="Permission denied")
        return report

    async def run(report: type[ReportView]) -> ReportTable:
        result = await report.run(_session_source(admin))
        return build_table(report, result)

    def attachment(report: type[ReportView], extension: str) -> dict[str, str]:
        # The slug is URL-safe ([a-z0-9_-]), so it needs no quoting here.
        return {"Content-Disposition": f"attachment; filename={report.slug}.{extension}"}

    @router.get("/", name="reports-index", response_class=HTMLResponse)
    async def reports_index(request: Request) -> Response:
        reports = [r for r in registered_reports() if await can_view(admin, request, r)]
        return admin.templates.TemplateResponse(request, "reports/list.html", {"reports": reports})

    @router.get("/{slug}/", name="report-detail", response_class=HTMLResponse)
    async def report_detail(request: Request, slug: str) -> Response:
        report = await authorized(request, slug)
        table = await run(report)
        return admin.templates.TemplateResponse(
            request, "reports/detail.html", {"report": report, "table": table}
        )

    @router.get("/{slug}/export.csv", name="report-export-csv")
    async def report_export_csv(request: Request, slug: str) -> Response:
        report = await authorized(request, slug)
        table = await run(report)
        return StreamingResponse(
            stream_csv(table), media_type="text/csv", headers=attachment(report, "csv")
        )

    @router.get("/{slug}/export.xlsx", name="report-export-xlsx")
    async def report_export_xlsx(request: Request, slug: str) -> Response:
        report = await authorized(request, slug)
        table = await run(report)
        # ``ReportView.filters`` is not applied until the filter library lands, so
        # the cover sheet honestly lists no filters.
        return StreamingResponse(
            stream_xlsx(table, title=report.get_label()),
            media_type=XLSX_MEDIA_TYPE,
            headers=attachment(report, "xlsx"),
        )

    return router

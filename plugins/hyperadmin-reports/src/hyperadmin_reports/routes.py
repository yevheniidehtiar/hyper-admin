"""Admin pages for registered reports: an index, the HTML grid and CSV / XLSX exports.

:func:`build_router` returns a plain ``APIRouter`` the plugin hands to
``admin.plugins.add_page``; ``Admin.mount()`` rebuilds it on the admin's
``HyperAdminRoute`` under ``{prefix}/reports``, so the routes run inside the
admin sub-app with its session, user, CSRF guard and error pages. Route names
join the ``hyperadmin:`` namespace (``hyperadmin:report-detail``, ...).

Every report route checks the report's codename (default ``view_report_{slug}``)
through the same permission checker the admin hands to its model views: the
built-in ``ModelPermissionChecker``, or the bridge checker with ``auth=``.
A user who lacks it gets the plugin's own 403 card, which names the permission
to ask for. Without auth every report is open, as model views are.

``?period=`` (``auto`` or a bucket period) overrides the declared period of the
report's time buckets for that request; the export links carry the page's
query string, so a download matches what is on screen.

``GET {slug}/chart`` is the chart fragment: the report's chart frame (see
:mod:`hyperadmin_reports.chart_data`), run with the same query string as the page, so the
chart and the grid always show the same period. The report page lazy-loads it over HTMX
(``?embed=1`` hides the frame's own period switch, the page's "Group by" control being the
authority there); embedded in a host template, the frame's switch re-requests the fragment.
A chart that cannot be drawn or a query that fails renders the frame's error state with a
200 status, because HTMX does not swap error responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.responses import Response

from hyperadmin.views.urls import admin_url_for
from hyperadmin_reports.bucketing import PERIODS, TimeBucket, describe_span
from hyperadmin_reports.chart_data import ChartUnavailableError, build_chart, chartable, placeholder
from hyperadmin_reports.charts import PeriodOption
from hyperadmin_reports.export import XLSX_MEDIA_TYPE, flatten_grid, stream_csv, stream_xlsx
from hyperadmin_reports.grid import build_grid
from hyperadmin_reports.view import get_report, registered_reports

if TYPE_CHECKING:
    from hyperadmin_reports.bucketing import PeriodOrAuto
    from hyperadmin_reports.export import ReportTable
    from hyperadmin_reports.view import ReportResult, ReportView, SessionSource

#: ``?period=`` values the bucket switch offers, in display order.
PERIOD_CHOICES: tuple[PeriodOrAuto, ...] = ("auto", *PERIODS)

logger = logging.getLogger(__name__)

#: Element the bucket switch swaps when HTMX is active (the whole report page).
PAGE_TARGET = "#report-page"


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


def parse_period(value: str | None) -> PeriodOrAuto | None:
    """The ``?period=`` override, or ``None`` when absent or not a known period."""
    if value in PERIOD_CHOICES:
        return value  # type: ignore[return-value]
    return None


def _time_bucket(report: type[ReportView]) -> TimeBucket | None:
    """The first time bucket of ``report`` (columns first), which the switch drives."""
    for dim in (*report.cols, *report.rows):
        if isinstance(dim, TimeBucket):
            return dim
    return None


def _page_url(request: Request, **changes: str) -> str:
    """The page's path with its query string, with ``changes`` applied."""
    return f"{request.url.path}?{urlencode({**request.query_params, **changes})}"


def chart_periods(
    request: Request, report: type[ReportView], override: PeriodOrAuto | None
) -> list[PeriodOption]:
    """The chart frame's period switch: links to this fragment, ``[]`` without a time bucket."""
    bucket = _time_bucket(report)
    if bucket is None:
        return []
    selected = override or bucket.period
    return [
        PeriodOption(value.capitalize(), _page_url(request, period=value), value == selected)
        for value in PERIOD_CHOICES
    ]


def bucket_switch(
    request: Request, report: type[ReportView], result: ReportResult, override: PeriodOrAuto | None
) -> dict[str, Any] | None:
    """Context of the "Group by" segmented control, or ``None`` without a time bucket.

    Every option is a plain link to ``?period=<value>`` (it works without
    JavaScript) upgraded with ``hx-get`` to swap the page in place. When the
    effective choice is ``auto``, ``note`` says which bucket it picked and why.
    """
    bucket = _time_bucket(report)
    if bucket is None:
        return None
    selected = override or bucket.period
    options = []
    for value in PERIOD_CHOICES:
        href = _page_url(request, period=value)
        options.append(
            {
                "value": value,
                "label": value.capitalize(),
                "selected": value == selected,
                "href": href,
                "attrs": {
                    "hx-get": href,
                    "hx-target": PAGE_TARGET,
                    "hx-swap": "outerHTML",
                    "hx-push-url": "true",
                },
            }
        )
    note = None
    if selected == "auto":
        chosen = result.periods[bucket.name]
        days = result.auto_spans.get(bucket.name)
        note = (
            f"Auto: {chosen}, for a {describe_span(days)} range"
            if days is not None
            else f"Auto: {chosen}, no dated rows to span"
        )
    return {"options": options, "note": note, "selected": selected}


def build_router(admin: Any) -> APIRouter:
    """The reports page router; ``admin`` is read per request, so it may be half-built here."""
    router = APIRouter()

    def forbidden(request: Request, report: type[ReportView]) -> Response:
        """The 403 card naming the permission to ask for, rendered by the plugin."""
        return admin.templates.TemplateResponse(
            request,
            "reports/forbidden.html",
            {
                "report": report,
                "codename": report.get_permission(),
                "permission_name": f"Can view report {report.get_label()}",
            },
            status_code=403,
        )

    async def authorized(request: Request, slug: str) -> type[ReportView] | Response:
        report = get_report(slug)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        if not await can_view(admin, request, report):
            return forbidden(request, report)
        return report

    async def run(report: type[ReportView], period: str | None) -> ReportResult:
        return await report.run(_session_source(admin), period=parse_period(period))

    async def table(report: type[ReportView], period: str | None) -> ReportTable:
        return flatten_grid(build_grid(report, await run(report, period)))

    def attachment(report: type[ReportView], extension: str) -> dict[str, str]:
        # The slug is URL-safe ([a-z0-9_-]), so it needs no quoting here.
        return {"Content-Disposition": f"attachment; filename={report.slug}.{extension}"}

    @router.get("/", name="reports-index", response_class=HTMLResponse)
    async def reports_index(request: Request) -> Response:
        reports = [r for r in registered_reports() if await can_view(admin, request, r)]
        return admin.templates.TemplateResponse(request, "reports/list.html", {"reports": reports})

    @router.get("/{slug}/", name="report-detail", response_class=HTMLResponse)
    async def report_detail(request: Request, slug: str, period: str | None = None) -> Response:
        report = await authorized(request, slug)
        if isinstance(report, Response):
            return report
        override = parse_period(period)
        result = await run(report, period)
        # The bucket each TimeBucket ran with ("auto" already resolved), by dimension label.
        periods = [
            (dim.label, result.periods[dim.name])
            for dim in (*report.rows, *report.cols)
            if dim.name in result.periods
        ]
        query = f"?{request.url.query}" if request.url.query else ""
        chart = None
        if chartable(report) and result.records:
            chart = {
                "url": admin_url_for(request, "report-chart", slug=slug).path,
                "query": f"?{urlencode({**request.query_params, 'embed': '1'})}",
                "placeholder": placeholder(report),
            }
        template = (
            "reports/_page.html" if request.headers.get("hx-request") else "reports/detail.html"
        )
        return admin.templates.TemplateResponse(
            request,
            template,
            {
                "report": report,
                "grid": build_grid(report, result),
                "periods": periods,
                "bucket": bucket_switch(request, report, result, override),
                "export_query": query,
                "chart": chart,
            },
        )

    @router.get("/{slug}/chart", name="report-chart", response_class=HTMLResponse)
    async def report_chart(
        request: Request, slug: str, period: str | None = None, embed: str | None = None
    ) -> Response:
        report = await authorized(request, slug)
        if isinstance(report, Response):
            return report
        context: dict[str, Any] = {"state": "ready", "message": "", "caption": "", "periods": []}
        try:
            built = build_chart(report, await run(report, period))
        except ChartUnavailableError as exc:
            context |= {"state": "error", "chart": placeholder(report), "message": str(exc)}
        except SQLAlchemyError:
            logger.exception("report %s: chart query failed", report.slug)
            query = f"?{request.url.query}" if request.url.query else ""
            context |= {
                "state": "error",
                "chart": placeholder(report),
                "message": "The report query failed.",
                "retry_url": f"{request.url.path}{query}",
            }
        else:
            context |= {"chart": built.chart, "caption": built.caption}
            if embed is None:
                context["periods"] = chart_periods(request, report, parse_period(period))
        return admin.templates.TemplateResponse(request, "reports/chart.html", context)

    @router.get("/{slug}/export.csv", name="report-export-csv")
    async def report_export_csv(request: Request, slug: str, period: str | None = None) -> Response:
        report = await authorized(request, slug)
        if isinstance(report, Response):
            return report
        return StreamingResponse(
            stream_csv(await table(report, period)),
            media_type="text/csv",
            headers=attachment(report, "csv"),
        )

    @router.get("/{slug}/export.xlsx", name="report-export-xlsx")
    async def report_export_xlsx(
        request: Request, slug: str, period: str | None = None
    ) -> Response:
        report = await authorized(request, slug)
        if isinstance(report, Response):
            return report
        # ``ReportView.filters`` is not applied until the filter library lands, so
        # the cover sheet lists only the period override, when there is one.
        override = parse_period(period)
        filters = {"period": override} if override else None
        return StreamingResponse(
            stream_xlsx(await table(report, period), title=report.get_label(), filters=filters),
            media_type=XLSX_MEDIA_TYPE,
            headers=attachment(report, "xlsx"),
        )

    return router

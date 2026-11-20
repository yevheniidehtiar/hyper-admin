"""Dashboard widgets: the base class, the built-in widgets and the widget registry.

A widget is one card of the dashboard. The data widgets bind to registered
reports: :class:`StatWidget` shows one total of a report aggregate and
:class:`ChartWidget` embeds the report's chart fragment, so every number on the
dashboard comes from the same query, totals and permission as its report page.
:class:`QuickActionsWidget` shows shortcut links. Hosts write their own by
subclassing :class:`DashboardWidget`.

Widgets are declared in code and registered with :func:`register_widget`
before ``Admin(...)`` is built, like reports; registration order is the default
order of the dashboard. A widget's ``key`` is its identity in saved layouts.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple

from hyperadmin.views.urls import admin_url_for
from hyperadmin_reports.admin_context import has_permission, session_source
from hyperadmin_reports.chart_data import chartable
from hyperadmin_reports.view import get_report

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from starlette.requests import Request

    from hyperadmin_reports.aggregates import Aggregate
    from hyperadmin_reports.view import ReportView

#: Grid columns a widget may span.
MIN_SPAN, MAX_SPAN = 1, 4
#: The lazy placeholder: a skeleton that loads ``fragment_url`` over HTMX.
LAZY_TEMPLATE = "dashboard/_lazy.html"

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class WidgetBody(NamedTuple):
    """What a widget renders inside its card: a template and its context."""

    template: str
    context: dict[str, Any]


class DashboardWidget(ABC):
    """One card of the dashboard.

    ``key`` (``[a-z0-9][a-z0-9_-]*``, unique) is the widget's identity in URLs
    and saved layouts; ``span`` is the number of grid columns (1..4). A
    ``lazy`` widget's body is loaded in its own HTMX request from
    :meth:`fragment_url`, so a slow or failing widget never holds the page
    back; a widget with ``lazy = False`` is rendered with the page.
    """

    key: str
    title: str
    span: int = 1
    lazy: ClassVar[bool] = True
    #: Text of the link to :meth:`detail_url`.
    detail_label: ClassVar[str] = "Open"
    #: ``data-testid`` of the card body, when tests need to find it.
    body_testid: ClassVar[str | None] = None

    def permission(self) -> str | None:
        """Codename a user must hold to see the widget; ``None`` shows it to everyone."""
        return None

    def fragment_url(self, request: Request) -> str:
        """URL the card body is loaded from (default: the dashboard's widget route)."""
        return admin_url_for(request, "dashboard-widget", key=self.key).path

    def detail_url(self, request: Request) -> str | None:  # noqa: ARG002 - overridden
        """URL of the page behind the widget (the card's link), or ``None``."""
        return None

    def validate(self) -> None:
        """Raise ``ValueError`` if the widget cannot be registered."""
        key = getattr(self, "key", None)
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise ValueError(f"{type(self).__name__}.key {key!r} is not URL-safe")
        if not getattr(self, "title", ""):
            raise ValueError(f"widget {key!r} needs a title")
        span = self.span
        if isinstance(span, bool) or not isinstance(span, int) or not MIN_SPAN <= span <= MAX_SPAN:
            raise ValueError(f"widget {key!r}: span must be {MIN_SPAN}..{MAX_SPAN}, got {span!r}")

    @abstractmethod
    async def render(self, request: Request, admin: Any) -> WidgetBody:
        """The card body. Exceptions are contained by the dashboard (an error state)."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}({getattr(self, 'key', None)!r})"


class _ReportWidget(DashboardWidget):
    """A widget bound to a registered report: its permission and its link are the report's."""

    detail_label: ClassVar[str] = "Open report"
    report: type[ReportView]

    def permission(self) -> str | None:
        return self.report.get_permission()

    def detail_url(self, request: Request) -> str | None:
        return admin_url_for(request, "report-detail", slug=self.report.slug).path

    def validate(self) -> None:
        super().validate()
        if get_report(self.report.slug) is not self.report:
            raise ValueError(
                f"widget {self.key!r}: report {self.report.__name__} is not registered; "
                "call register_report() first"
            )


class StatWidget(_ReportWidget):
    """One number: the grand total of a report aggregate.

    ``value`` names the aggregate (``Aggregate.name``, e.g. ``"sum_amount"``);
    by default it is the report's first aggregate that has totals. The key
    defaults to ``stat-{slug}`` and the title to the aggregate's label.
    """

    def __init__(
        self,
        report: type[ReportView],
        *,
        value: str | None = None,
        key: str | None = None,
        title: str | None = None,
        span: int = 1,
    ) -> None:
        self.report = report
        self.aggregate = _stat_aggregate(report, value)
        self.key = key or f"stat-{report.slug}"
        self.title = title or self.aggregate.label
        self.span = span

    async def render(self, request: Request, admin: Any) -> WidgetBody:
        result = await self.report.run(session_source(admin))
        name = self.aggregate.name
        value = self.aggregate.total(record[name] for record in result.records)
        return WidgetBody(
            "dashboard/_stat.html",
            {
                "widget": self,
                "value": value,
                "report": self.report,
                "detail_url": self.detail_url(request),
            },
        )


class ChartWidget(_ReportWidget):
    """The report's chart, loaded from the report's own chart fragment.

    The card requests ``{prefix}/reports/{slug}/chart?embed=1``, so the chart,
    its no-data and error states and its permission check are the report's.
    The key defaults to ``chart-{slug}`` and the title to the report's label.
    """

    body_testid: ClassVar[str | None] = "report-chart"

    def __init__(
        self,
        report: type[ReportView],
        *,
        key: str | None = None,
        title: str | None = None,
        span: int = 2,
    ) -> None:
        if not chartable(report):
            raise ValueError(
                f"{report.__name__} cannot be drawn as a chart: it needs a row or column "
                "dimension and an aggregate with totals"
            )
        self.report = report
        self.key = key or f"chart-{report.slug}"
        self.title = title or report.get_label()
        self.span = span

    def fragment_url(self, request: Request) -> str:
        return f"{admin_url_for(request, 'report-chart', slug=self.report.slug).path}?embed=1"

    async def render(self, request: Request, admin: Any) -> WidgetBody:  # noqa: ARG002
        """The lazy placeholder: the chart itself comes from :meth:`fragment_url`."""
        return WidgetBody(
            LAZY_TEMPLATE,
            {
                "widget": self,
                "fragment_url": self.fragment_url(request),
                "detail_url": self.detail_url(request),
            },
        )


@dataclass(frozen=True)
class QuickAction:
    """A shortcut link: a named admin route, shown only to users holding ``permission``."""

    label: str
    #: Route name, resolved in the ``hyperadmin:`` namespace (e.g. ``"order-create-form"``).
    url_name: str
    url_params: Mapping[str, Any] = field(default_factory=dict)
    permission: str | None = None
    #: Name of an icon of the admin's icon set.
    icon: str | None = None


class QuickActionsWidget(DashboardWidget):
    """Shortcut links, rendered with the page (no query, so nothing to load lazily)."""

    lazy: ClassVar[bool] = False

    def __init__(
        self,
        actions: Sequence[QuickAction],
        *,
        key: str = "quick-actions",
        title: str = "Quick actions",
        span: int = 1,
    ) -> None:
        self.actions = tuple(actions)
        self.key = key
        self.title = title
        self.span = span

    async def render(self, request: Request, admin: Any) -> WidgetBody:
        links = [
            {
                "label": action.label,
                "url": admin_url_for(request, action.url_name, **action.url_params).path,
                "icon": action.icon,
            }
            for action in self.actions
            if await has_permission(admin, request, action.permission)
        ]
        return WidgetBody("dashboard/_actions.html", {"widget": self, "actions": links})


def _stat_aggregate(report: type[ReportView], value: str | None) -> Aggregate:
    """The aggregate a :class:`StatWidget` totals; ``ValueError`` when there is none."""
    if value is None:
        found = next((a for a in report.values if a.totals), None)
        if found is None:
            raise ValueError(f"{report.__name__} has no aggregate with totals to show as a stat")
        return found
    named = next((a for a in report.values if a.name == value), None)
    if named is None:
        names = ", ".join(a.name for a in report.values)
        raise ValueError(f"{report.__name__} has no aggregate {value!r} (it has: {names})")
    if not named.totals:
        raise ValueError(f"{report.__name__}.{value} has no totals, so it cannot be a stat")
    return named


_WIDGETS: dict[str, DashboardWidget] = {}


def register_widget(widget: DashboardWidget) -> DashboardWidget:
    """Validate ``widget``, add it to the dashboard and return it unchanged.

    Raises ``ValueError`` at registration time instead of on the first request:
    a key that is not URL-safe or that another widget holds, a span outside
    1..4, or a report-bound widget whose report is not registered. Registering
    the same instance twice is a no-op.

    Register widgets before ``Admin(...)`` is built, after their reports: the
    plugin decides while the admin loads whether there is a dashboard to serve.
    """
    widget.validate()
    existing = _WIDGETS.get(widget.key)
    if existing is not None and existing is not widget:
        raise ValueError(f"widget key {widget.key!r} is already registered by {existing!r}")
    _WIDGETS[widget.key] = widget
    return widget


def unregister_widget(widget: DashboardWidget | str) -> None:
    """Remove a widget (or the widget holding a key); a no-op if it is not registered."""
    if isinstance(widget, str):
        _WIDGETS.pop(widget, None)
    elif _WIDGETS.get(widget.key) is widget:
        del _WIDGETS[widget.key]


def registered_widgets() -> list[DashboardWidget]:
    """Registered widgets in registration order, which is the default dashboard order."""
    return list(_WIDGETS.values())


def get_widget(key: str) -> DashboardWidget | None:
    """The widget registered under ``key``, or ``None``."""
    return _WIDGETS.get(key)

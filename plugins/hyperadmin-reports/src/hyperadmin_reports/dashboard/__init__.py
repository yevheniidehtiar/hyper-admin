"""The dashboard: report numbers, report charts and shortcut links on the admin home page.

SDD: ``docs/specs/dashboard-builder.md``. The public names are re-exported
from :mod:`hyperadmin_reports`.
"""

from hyperadmin_reports.dashboard.layout import (
    LayoutStore,
    LayoutUnavailableError,
    create_layout_table,
    dashboard_metadata,
)
from hyperadmin_reports.dashboard.service import DashboardService, LayoutRejectedError
from hyperadmin_reports.dashboard.widgets import (
    ChartWidget,
    DashboardWidget,
    QuickAction,
    QuickActionsWidget,
    StatWidget,
    WidgetBody,
    get_widget,
    register_widget,
    registered_widgets,
    unregister_widget,
)

__all__ = [
    "ChartWidget",
    "DashboardService",
    "DashboardWidget",
    "LayoutRejectedError",
    "LayoutStore",
    "LayoutUnavailableError",
    "QuickAction",
    "QuickActionsWidget",
    "StatWidget",
    "WidgetBody",
    "create_layout_table",
    "dashboard_metadata",
    "get_widget",
    "register_widget",
    "registered_widgets",
    "unregister_widget",
]

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

__all__ = [
    "LayoutStore",
    "LayoutUnavailableError",
    "create_layout_table",
    "dashboard_metadata",
]

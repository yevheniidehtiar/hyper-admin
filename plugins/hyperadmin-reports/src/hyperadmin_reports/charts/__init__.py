"""Server-rendered SVG charts for reports.

The chart classes compute geometry; the Jinja macros in
``hyperadmin_reports/templates/hyperadmin_reports/charts/`` draw it, styled by
``hyperadmin_reports/static/hyperadmin_reports/charts.css``. Both directories are served
once the core plugin registry wires plugin template and static paths into the admin.
"""

from hyperadmin_reports.charts.geometry import (
    BarChart,
    Chart,
    LineChart,
    PeriodOption,
    Series,
    Sparkline,
    StackedBarChart,
)

__all__ = [
    "BarChart",
    "Chart",
    "LineChart",
    "PeriodOption",
    "Series",
    "Sparkline",
    "StackedBarChart",
]

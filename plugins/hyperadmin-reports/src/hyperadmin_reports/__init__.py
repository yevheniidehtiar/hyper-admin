"""Declarative OLAP-style reports: aggregates, crosstab pivots and time bucketing."""

from hyperadmin_reports.aggregates import (
    Aggregate,
    Count,
    Many2One,
    Max,
    Min,
    StringAggComma,
    Sum,
)
from hyperadmin_reports.bucketing import AUTO_THRESHOLDS, Period, TimeBucket, resolve_period
from hyperadmin_reports.cache import FactTableSource
from hyperadmin_reports.crosstab import Pivot, pivot
from hyperadmin_reports.export import ReportTable, build_table, stream_csv, stream_xlsx
from hyperadmin_reports.view import (
    Dimension,
    Group,
    ReportResult,
    ReportView,
    get_report,
    register_report,
    registered_reports,
    unregister_report,
)

__all__ = [
    "AUTO_THRESHOLDS",
    "Aggregate",
    "Count",
    "Dimension",
    "FactTableSource",
    "Group",
    "Many2One",
    "Max",
    "Min",
    "Period",
    "Pivot",
    "ReportResult",
    "ReportTable",
    "ReportView",
    "StringAggComma",
    "Sum",
    "TimeBucket",
    "build_table",
    "get_report",
    "pivot",
    "register_report",
    "registered_reports",
    "resolve_period",
    "stream_csv",
    "stream_xlsx",
    "unregister_report",
]

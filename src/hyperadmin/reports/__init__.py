"""Declarative OLAP-style reports: aggregates, crosstab pivots and time bucketing."""

from hyperadmin.reports.aggregates import (
    Aggregate,
    Count,
    Many2One,
    Max,
    Min,
    StringAggComma,
    Sum,
)
from hyperadmin.reports.bucketing import AUTO_THRESHOLDS, Period, TimeBucket, resolve_period
from hyperadmin.reports.crosstab import Pivot, pivot
from hyperadmin.reports.view import Dimension, Group, ReportResult, ReportView

__all__ = [
    "AUTO_THRESHOLDS",
    "Aggregate",
    "Count",
    "Dimension",
    "Group",
    "Many2One",
    "Max",
    "Min",
    "Period",
    "Pivot",
    "ReportResult",
    "ReportView",
    "StringAggComma",
    "Sum",
    "TimeBucket",
    "pivot",
    "resolve_period",
]

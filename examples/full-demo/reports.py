"""OLAP reports over the order items (H14) and their chart binding (H15)."""

from typing import ClassVar

from models import OrderItem

from hyperadmin_reports import Group, ReportView, Sum, TimeBucket, register_report


class SalesBySku(ReportView):
    """Revenue per SKU and month; the period switch regroups it by quarter or year."""

    slug = "sales-by-sku"
    label = "Sales by SKU"
    description = "Revenue per SKU, bucketed by month."
    model = OrderItem
    rows: ClassVar = [Group("sku")]
    cols: ClassVar = [TimeBucket("sold_at", period="month")]
    values: ClassVar = [Sum("amount")]


def register_reports() -> None:
    register_report(SalesBySku)

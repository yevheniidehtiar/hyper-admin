"""The ERP's pivot reports, listed on the ``hyperadmin-reports`` "All reports" page.

The Profit & Loss page (``views.py``) and the dashboard figures are hand-built pages,
not ``ReportView`` declarations, so the reports plugin cannot list them. These reports
give its index real content: invoices and bills counted per status and month.

``register_reports()`` must run before ``Admin(...)`` is built: the plugin declares each
report's ``view_report_<slug>`` permission and sidebar link while the admin loads it.
"""

from __future__ import annotations

from typing import ClassVar

from examples.erp.purchases.models import Bill
from examples.erp.sales.models import Invoice

try:
    from hyperadmin_reports import Count, Group, ReportView, TimeBucket, register_report
except ImportError:  # the reports plugin is an optional workspace package
    register_report = None  # type: ignore[assignment]
else:

    class InvoicesByStatus(ReportView):
        """How many invoices were issued per month, split by status."""

        slug = "invoices-by-status"
        label = "Invoices by status"
        description = "Invoices issued per month, by status."
        model = Invoice
        rows: ClassVar = [Group("status")]
        cols: ClassVar = [TimeBucket("date_issued", period="month")]
        values: ClassVar = [Count()]

    class BillsByStatus(ReportView):
        """How many supplier bills were received per month, split by status."""

        slug = "bills-by-status"
        label = "Bills by status"
        description = "Supplier bills received per month, by status."
        model = Bill
        rows: ClassVar = [Group("status")]
        cols: ClassVar = [TimeBucket("date_received", period="month")]
        values: ClassVar = [Count()]


def register_reports() -> None:
    """Register the ERP reports with the reports plugin, when it is installed."""
    if register_report is None:
        return
    register_report(InvoicesByStatus)
    register_report(BillsByStatus)

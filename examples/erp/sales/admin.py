from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from examples.erp.sales.models import Invoice, InvoiceItem, InvoiceStatus, TaxRate
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.filters import DateRangeFilter, MultiFKFilter
from hyperadmin.panels import pdf_stream_panel

if TYPE_CHECKING:
    from fastapi import Request

# The bundled streaming demo (docs/specs/detail-panels.md): an issued invoice's detail
# page gets an "Invoice" tab that shows this sample PDF inline. Drafts have no tab.
SAMPLE_PDF = Path(__file__).resolve().parents[3] / "tests" / "_fixtures" / "sample.pdf"


class InvoiceAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    nav_group = "Sales"
    nav_order = 0
    icon = "receipt"
    list_display: ClassVar[list[str]] = [
        "number",
        "customer",
        "date_issued",
        "date_due",
        "status",
        "total_amount",
    ]
    # A clerk narrows 500 invoices by status, customer and due date. "Overdue" is the
    # Sent status with a due date before today (the status pill already reads "Overdue").
    list_filter: ClassVar[list[Any]] = [
        "status",
        MultiFKFilter(field="customer_id", label="Customer"),
        DateRangeFilter(field="date_due", label="Due date"),
    ]
    search_fields: ClassVar[list[str]] = ["number"]
    # Demonstrates AdminOptions.inlines: invoice items are edited directly on
    # the Invoice create/update page instead of needing a separate list page.
    options: ClassVar[AdminOptions] = AdminOptions(
        inlines=[
            InlineModelSpec(
                model=InvoiceItem,
                fk_field="invoice_id",
                relationship_name="items",
                extra=1,
                title="Invoice items",
            ),
        ],
        panels=[
            pdf_stream_panel(
                slug="invoice",
                label="Invoice",
                icon="file-text",
                path_resolver=lambda _invoice: SAMPLE_PDF,
                enabled=lambda invoice: invoice.status != InvoiceStatus.DRAFT,
            ),
        ],
    )

    @action(label="Mark paid", bulk=True)
    async def mark_paid(self, request: Request, item_id: int, *, params: Any = None) -> None:  # noqa: ARG002
        """Marks the selected invoices as paid."""
        await self.adapter.update(item_id, {"status": InvoiceStatus.PAID})


class InvoiceItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    nav_group = "Sales"
    nav_order = 1
    icon = "file-text"
    list_display: ClassVar[list[str]] = [
        "invoice",
        "description",
        "quantity",
        "unit_price",
        "total_price",
    ]


class TaxRateAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    nav_group = "Sales"
    nav_order = 2
    icon = "tag"
    list_display: ClassVar[list[str]] = ["id", "name", "rate"]
    search_fields: ClassVar[list[str]] = ["name"]


site.register(Invoice, InvoiceAdmin)
site.register(InvoiceItem, InvoiceItemAdmin)
site.register(TaxRate, TaxRateAdmin)

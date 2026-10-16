from __future__ import annotations

from typing import ClassVar

from examples.erp.sales.models import Invoice, InvoiceItem, TaxRate
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site


class InvoiceAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = [
        "number",
        "customer",
        "date_issued",
        "date_due",
        "status",
        "total_amount",
    ]
    list_filter: ClassVar[list[str]] = ["status"]
    search_fields: ClassVar[list[str]] = ["number"]
    # Demonstrates AdminOptions.inlines: invoice items are edited directly on
    # the Invoice create/update page instead of needing a separate list page.
    options: ClassVar[AdminOptions] = AdminOptions(
        inlines=[
            InlineModelSpec(
                model=InvoiceItem,
                fk_field="invoice_id",
                relationship_name="items",
                extra=2,
                title="Invoice items",
            ),
        ],
    )


class InvoiceItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = [
        "invoice",
        "description",
        "quantity",
        "unit_price",
        "total_price",
    ]


class TaxRateAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = ["id", "name", "rate"]
    search_fields: ClassVar[list[str]] = ["name"]


site.register(Invoice, InvoiceAdmin)
site.register(InvoiceItem, InvoiceItemAdmin)
site.register(TaxRate, TaxRateAdmin)

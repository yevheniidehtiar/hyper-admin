from __future__ import annotations

from typing import ClassVar

from examples.erp.sales.models import Invoice, InvoiceItem, TaxRate
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
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

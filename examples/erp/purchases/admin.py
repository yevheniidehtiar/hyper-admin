from __future__ import annotations

from typing import ClassVar

from examples.erp.purchases.models import Bill, BillItem
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class BillAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = [
        "reference",
        "supplier",
        "date_received",
        "date_due",
        "status",
        "total_amount",
    ]
    list_filter: ClassVar[list[str]] = ["status"]
    search_fields: ClassVar[list[str]] = ["reference"]


class BillItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = [
        "bill",
        "description",
        "quantity",
        "unit_price",
        "total_price",
    ]


site.register(Bill, BillAdmin)
site.register(BillItem, BillItemAdmin)

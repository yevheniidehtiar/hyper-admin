from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from fastapi import HTTPException

from examples.erp.filters import OverdueFilter
from examples.erp.purchases.models import Bill, BillItem, BillStatus
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.filters import DateRangeFilter, MultiFKFilter

if TYPE_CHECKING:
    from fastapi import Request


class BillAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    nav_group = "Purchases"
    nav_order = 0
    icon = "credit-card"
    list_display: ClassVar[list[str]] = [
        "reference",
        "supplier",
        "date_received",
        "date_due",
        "status",
        "total_amount",
    ]
    list_filter: ClassVar[list[Any]] = [
        "status",
        MultiFKFilter(field="supplier_id", label="Supplier"),
        DateRangeFilter(field="date_due", label="Due date"),
        OverdueFilter(field="date_due", open_status=BillStatus.TO_PAY),
    ]
    search_fields: ClassVar[list[str]] = ["reference"]

    @action(label="Mark paid", bulk=True)
    async def mark_paid(self, request: Request, item_id: int, *, params: Any = None) -> None:  # noqa: ARG002
        """Marks the selected To Pay bills as paid; other statuses are refused."""
        bill = await self.adapter.get(item_id)
        if bill is None or bill.status != BillStatus.TO_PAY:
            raise HTTPException(status_code=409, detail="Only bills to pay can be marked paid")
        await self.adapter.update(item_id, {"status": BillStatus.PAID})


class BillItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    nav_group = "Purchases"
    nav_order = 1
    icon = "package"
    list_display: ClassVar[list[str]] = [
        "bill",
        "description",
        "quantity",
        "unit_price",
        "total_price",
    ]


site.register(Bill, BillAdmin)
site.register(BillItem, BillItemAdmin)

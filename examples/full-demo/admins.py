"""ModelAdmin registrations for the full-demo umbrella app."""

from pathlib import Path
from typing import Any, ClassVar

from fastapi import HTTPException
from models import Invoice, Order, OrderItem, Product, Supplier, Variant
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions, RelationDependency
from hyperadmin.core.panels import panel
from hyperadmin.core.registry import site
from hyperadmin.filters import BooleanFilter, DateRangeFilter, IsOwnerFilter, MultiFKFilter
from hyperadmin.panels import pdf_stream_panel

SAMPLE_PDF = Path(__file__).resolve().parent / "static" / "sample.pdf"


class SupplierAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class VariantAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class ProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options: ClassVar[AdminOptions] = AdminOptions(
        list_display=["name", "supplier_id", "variant_id", "cover_image"],
        relation_filters={
            "variant_id": RelationDependency(
                depends_on="supplier_id", placeholder="Pick a supplier first"
            )
        },
        relation_display={"supplier_id": "{name} — {city}"},
    )


class OrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options: ClassVar[AdminOptions] = AdminOptions(
        list_display=["number", "status", "created_on", "paid", "locked"],
        list_filter=[
            DateRangeFilter(field="created_on"),
            MultiFKFilter(field="supplier_id"),
            BooleanFilter(field="paid"),
            IsOwnerFilter(owner_fields="created_by"),
        ],
        inlines=[
            InlineModelSpec(
                model=OrderItem,
                fk_field="order_id",
                relationship_name="order_items",
                fields=["sku", "quantity", "amount"],
                extra=0,
                title="Order items",
            )
        ],
        panels=[
            pdf_stream_panel(
                slug="invoice",
                label="Invoice",
                icon="file-text",
                path_resolver=lambda _order: SAMPLE_PDF,
            ),
        ],
    )

    @panel(label="History", icon="clock")
    async def history(self, request: Request, obj: Any) -> Response:  # noqa: ARG002
        return HTMLResponse(f'<p data-testid="history-body">Order {obj.number} was created.</p>')

    @panel(label="Transitions", icon="git-branch")
    async def transitions(self, request: Request, obj: Any) -> Response:  # noqa: ARG002
        return HTMLResponse(
            f'<p data-testid="transitions-body">{obj.number}: new → {obj.status}.</p>'
        )

    @action(label="Archive", bulk=True)
    async def archive(
        self,
        request: Request,  # noqa: ARG002
        item_id: int,
        *,
        params: Any = None,  # noqa: ARG002
    ) -> None:
        """Archives the orders. A locked order refuses and is reported per row."""
        order = await self.adapter.get(item_id)
        if order.locked:
            raise HTTPException(status_code=403, detail="order is locked")
        await self.adapter.update(pk=item_id, data={"status": "archived"})


class InvoiceAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


def register_all() -> None:
    """Register every demo model with the global admin site."""
    site._registry = {}
    site.register(Supplier, SupplierAdmin)
    site.register(Variant, VariantAdmin)
    site.register(Product, ProductAdmin)
    site.register(Order, OrderAdmin)
    site.register(Invoice, InvoiceAdmin)

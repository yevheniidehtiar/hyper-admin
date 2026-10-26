"""Generic domain models for the full-demo umbrella app.

Only framework-neutral names are used (Supplier, Variant, Product, Order, OrderItem,
Invoice) so the app doubles as a readiness check for any downstream project.
"""

# No `from __future__ import annotations`: SQLModel resolves `Mapped[...]` relationship
# annotations at class creation and cannot evaluate them as strings.
import tempfile
from datetime import date, datetime, timezone

from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import ImageType
from sqlalchemy import Column
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

#: Where uploaded product images land (a fresh temp dir per process).
upload_storage = FileSystemStorage(tempfile.mkdtemp(prefix="hyperadmin_full_demo_uploads_"))


class Supplier(SQLModel, table=True):
    __tablename__ = "fd_supplier"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    city: str | None = None


class Variant(SQLModel, table=True):
    __tablename__ = "fd_variant"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    supplier_id: int | None = Field(default=None, foreign_key="fd_supplier.id", title="Supplier")

    supplier: Mapped[Supplier | None] = Relationship()


class Product(SQLModel, table=True):
    __tablename__ = "fd_product"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    supplier_id: int | None = Field(default=None, foreign_key="fd_supplier.id", title="Supplier")
    variant_id: int | None = Field(default=None, foreign_key="fd_variant.id", title="Variant")
    cover_image: str | None = Field(
        default=None, sa_column=Column(ImageType(storage=upload_storage))
    )

    supplier: Mapped[Supplier | None] = Relationship()
    variant: Mapped[Variant | None] = Relationship()


class Order(SQLModel, table=True):
    __tablename__ = "fd_order"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(min_length=1)
    status: str = "new"
    created_on: date
    #: Owner's user key; ``IsOwnerFilter`` compares it with the signed-in user.
    created_by: str = ""
    supplier_id: int | None = Field(default=None, foreign_key="fd_supplier.id", title="Supplier")
    paid: bool = False
    #: A locked order refuses the bulk "Archive" action (the per-row failure demo).
    locked: bool = False

    supplier: Mapped[Supplier | None] = Relationship()
    order_items: Mapped[list["OrderItem"]] = Relationship()


class OrderItem(SQLModel, table=True):
    """Order line; also the fact table for the sales reports."""

    __tablename__ = "fd_order_item"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int | None = Field(default=None, foreign_key="fd_order.id")
    sku: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    amount: int = 0
    sold_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Invoice(SQLModel, table=True):
    __tablename__ = "fd_invoice"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(min_length=1)
    order_id: int | None = Field(default=None, foreign_key="fd_order.id", title="Order")
    total: int = 0

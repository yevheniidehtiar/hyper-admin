"""HTMX autocomplete fixture app for E2E testing (H6, v0.5.5).

Started by the ``autocomplete_base_url`` fixture via a uvicorn subprocess.
Spec: ``docs/specs/htmx-autocomplete.md`` (BDD scenarios); design:
``docs/design/system/components/AutocompleteStates``.

Auth is on (superuser ``alice / secret123``) so the CSRF guard applies to the
popup POST and the "+" button is gated by the ``add_supplier`` permission,
exactly as in a consumer admin.

Registered models:

* ``Supplier`` (``name``, ``city``) — the "+" popup target; the Product admin
  renders its options as ``"{name} — {city}"`` via ``relation_display``.
* ``Variant`` (``supplier_id`` FK) — the dependent field: ``relation_filters``
  makes ``Product.variant_id`` depend on ``Product.supplier_id`` with the
  placeholder "Pick a supplier first".
* ``Product`` — FKs to Supplier, Variant and Brand.

``Brand`` is deliberately *not* registered, so the ``brand_id`` widget has no
"+" button (scenario: popup hidden when the related model is unregistered).

Seeded rows: suppliers 42 "Acme" (Paris), 43 "Acme Packaging" (Lyon) and
44 "Brabant Bakkerij" (Tilburg); variants 1 "Blue" (supplier 42) and 2 "Red"
(supplier 43); brand 1 "Generic".
"""

# No `from __future__ import annotations`: SQLModel resolves `Mapped[...]` relationship
# annotations at class creation and cannot evaluate them as strings.
import os
import tempfile
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, ClassVar

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel, select

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions, RelationDependency
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_autocomplete_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


class Supplier(SQLModel, table=True):
    __tablename__ = "e2e_ac_supplier"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    city: str | None = None


class Variant(SQLModel, table=True):
    __tablename__ = "e2e_ac_variant"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    supplier_id: int | None = Field(
        default=None, foreign_key="e2e_ac_supplier.id", title="Supplier"
    )

    supplier: Mapped[Supplier | None] = Relationship()


class Brand(SQLModel, table=True):
    __tablename__ = "e2e_ac_brand"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)


class Product(SQLModel, table=True):
    __tablename__ = "e2e_ac_product"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    supplier_id: int | None = Field(
        default=None, foreign_key="e2e_ac_supplier.id", title="Supplier"
    )
    variant_id: int | None = Field(default=None, foreign_key="e2e_ac_variant.id", title="Variant")
    brand_id: int | None = Field(default=None, foreign_key="e2e_ac_brand.id", title="Brand")

    supplier: Mapped[Supplier | None] = Relationship()
    variant: Mapped[Variant | None] = Relationship()
    brand: Mapped[Brand | None] = Relationship()


class SupplierAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class VariantAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class ProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options: ClassVar[AdminOptions] = AdminOptions(
        relation_filters={
            "variant_id": RelationDependency(
                depends_on="supplier_id", placeholder="Pick a supplier first"
            )
        },
        relation_display={"supplier_id": "{name} — {city}"},
    )


async def _seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first() is None:
            session.add(
                User(
                    username="alice",
                    email="alice@example.com",
                    password_hash=hash_password("secret123"),
                    is_superuser=True,
                )
            )
        if (await session.execute(select(Supplier))).first() is None:
            session.add_all(
                [
                    Supplier(id=42, name="Acme", city="Paris"),
                    Supplier(id=43, name="Acme Packaging", city="Lyon"),
                    Supplier(id=44, name="Brabant Bakkerij", city="Tilburg"),
                    Variant(id=1, name="Blue", supplier_id=42),
                    Variant(id=2, name="Red", supplier_id=43),
                    Brand(id=1, name="Generic"),
                ]
            )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> "AsyncIterator[None]":
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)

settings = HyperAdminSettings(
    create_tables=False,
    secret_key="e2e-autocomplete-secret",
    auto_discover=False,
)

site._registry = {}
site.register(Supplier, SupplierAdmin)
site.register(Variant, VariantAdmin)
site.register(Product, ProductAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=settings,
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}

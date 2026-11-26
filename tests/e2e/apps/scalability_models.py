"""Models and seed plan of the scalability fixture app (#243).

Kept apart from :mod:`tests.e2e.apps.scalability` so the test process can build the database
(``seed_database``) without importing the app, which would create an ``Admin`` in the test
process. The rows come from the synthetic data generator (:mod:`hyperadmin.loadtest`), the same
one ``hyperadmin seed`` uses for load tests.

Tables and default sizes (12,605 rows):

* ``Warehouse`` - 5 rows. Small: a foreign key to it is a preloaded select.
* ``Supplier`` - 600 rows, above the default ``preload_threshold`` of 500: a foreign key to it
  is a lazy autocomplete.
* ``Product`` - 9,000 rows, each with a supplier and a warehouse.
* ``Movement`` - 3,000 rows, each pointing at a product.

``E2E_SCALABILITY_SCALE`` multiplies the ``Product`` and ``Movement`` counts (``100`` gives
1.2 million rows) for an opt-in large run; ``Warehouse`` and ``Supplier`` keep their size so
the widget thresholds stay on the same side.

Values are a function of the row number, so a test can name a row without reading the
database: product ``n`` (1-based primary key) has SKU ``SKU-{n-1:07d}``.
"""

# No `from __future__ import annotations`: SQLModel resolves `Mapped[...]` relationship
# annotations at class creation and cannot evaluate them as strings.
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.loadtest import BulkSeeder, SeedPlan, TablePlan

WAREHOUSES = 5
SUPPLIERS = 600
PRODUCTS = 9_000
MOVEMENTS = 3_000

_CITIES = ("Utrecht", "Gdansk", "Porto", "Lyon", "Tallinn")
_COUNTRIES = ("NL", "PL", "PT", "FR", "EE", "DE")


def scale() -> int:
    """Multiplier for the two large tables (``E2E_SCALABILITY_SCALE``, default 1)."""
    return max(1, int(os.environ.get("E2E_SCALABILITY_SCALE", "1")))


class Warehouse(SQLModel, table=True):
    __tablename__ = "e2e_sc_warehouse"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=40)
    city: str = Field(default="", max_length=40)

    def __str__(self) -> str:
        return self.name


class Supplier(SQLModel, table=True):
    __tablename__ = "e2e_sc_supplier"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=40)
    country: str = Field(default="", max_length=2)

    def __str__(self) -> str:
        return self.name


class Product(SQLModel, table=True):
    __tablename__ = "e2e_sc_product"

    id: int | None = Field(default=None, primary_key=True)
    sku: str = Field(min_length=1, max_length=20, unique=True, index=True)
    name: str = Field(min_length=1, max_length=60)
    price: float = Field(default=0.0)
    supplier_id: int | None = Field(
        default=None, foreign_key="e2e_sc_supplier.id", title="Supplier", index=True
    )
    warehouse_id: int | None = Field(
        default=None, foreign_key="e2e_sc_warehouse.id", title="Warehouse", index=True
    )

    supplier: Mapped[Supplier | None] = Relationship()
    warehouse: Mapped[Warehouse | None] = Relationship()

    def __str__(self) -> str:
        return self.sku


class Movement(SQLModel, table=True):
    __tablename__ = "e2e_sc_movement"

    id: int | None = Field(default=None, primary_key=True)
    reference: str = Field(min_length=1, max_length=20)
    quantity: int = Field(default=1)
    product_id: int | None = Field(
        default=None, foreign_key="e2e_sc_product.id", title="Product", index=True
    )

    product: Mapped[Product | None] = Relationship()

    def __str__(self) -> str:
        return self.reference


TABLES = (Warehouse, Supplier, Product, Movement)


def build_plan(multiplier: int = 1) -> SeedPlan:
    """Return the seed plan; ``multiplier`` scales ``Product`` and ``Movement``."""

    def warehouses(pool, rng, seq):
        return {"name": f"Warehouse {seq + 1}", "city": _CITIES[seq % len(_CITIES)]}

    def suppliers(pool, rng, seq):
        return {"name": f"Supplier {seq + 1:04d}", "country": rng.choice(_COUNTRIES)}

    def products(pool, rng, seq):
        return {
            "sku": f"SKU-{seq:07d}",
            "name": f"Product {seq:07d}",
            "price": round(rng.uniform(1.0, 500.0), 2),
            "supplier_id": pool.sample("e2e_sc_supplier"),
            "warehouse_id": pool.sample("e2e_sc_warehouse"),
        }

    def movements(pool, rng, seq):
        return {
            "reference": f"MOV-{seq:07d}",
            "quantity": rng.randint(1, 50),
            "product_id": pool.sample("e2e_sc_product"),
        }

    return SeedPlan(
        (
            TablePlan("e2e_sc_warehouse", WAREHOUSES, warehouses, ("name", "city")),
            TablePlan("e2e_sc_supplier", SUPPLIERS, suppliers, ("name", "country")),
            TablePlan(
                "e2e_sc_product",
                PRODUCTS * multiplier,
                products,
                ("sku", "name", "price", "supplier_id", "warehouse_id"),
                fk_parents=("e2e_sc_supplier", "e2e_sc_warehouse"),
                unique_columns=("sku",),
            ),
            TablePlan(
                "e2e_sc_movement",
                MOVEMENTS * multiplier,
                movements,
                ("reference", "quantity", "product_id"),
                fk_parents=("e2e_sc_product",),
            ),
        )
    )


def seed_database(path: Path, multiplier: int = 1) -> int:
    """Create the four tables in the SQLite file at ``path``, fill them and return the row count."""
    return seed_url(f"sqlite:///{path}", path.with_suffix(".seed.json"), multiplier)


def seed_url(url: str, state_file: Path, multiplier: int = 1) -> int:
    """Create the four tables in the database at ``url`` (a sync SQLAlchemy URL), fill them
    and return the row count. ``state_file`` is the seeder's resume checkpoint."""
    engine = create_engine(url)
    try:
        SQLModel.metadata.create_all(
            engine,
            tables=[model.__table__ for model in TABLES],  # type: ignore[attr-defined]
        )
        summary = BulkSeeder(
            plan=build_plan(multiplier),
            engine=engine,
            state_file=state_file,
            install_signal_handlers=False,
        ).run()
    finally:
        engine.dispose()
    return summary.rows_inserted

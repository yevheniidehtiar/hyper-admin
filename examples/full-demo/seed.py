"""Seed data for the full-demo umbrella app (idempotent).

Users (password ``secret123``): ``alice`` (superuser, user key ``1``), ``bob``
(superuser, key ``2``) and ``viewer`` (member of ``Viewers``, which holds
``view_order``, ``change_order`` and ``view_invoice``).

Orders ORD-1..ORD-5: alice owns 1, 3 and 5; bob 2 and 4; ORD-3 is locked, so a bulk
archive over all five fails on that one row only.
"""

from datetime import date, datetime, timezone

from models import Invoice, Order, OrderItem, Product, Supplier, Variant
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlmodel import select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import Group, GroupPermission, Permission, User, UserGroup

PASSWORD = "secret123"  # noqa: S105
VIEWER_PERMISSIONS = ("view_order", "change_order", "view_invoice")

#: (number, status, created_on, owner key, supplier id, paid, locked)
_ORDERS = (
    ("ORD-1", "new", date(2026, 1, 5), "1", 42, True, False),
    ("ORD-2", "shipped", date(2026, 1, 15), "2", 42, False, False),
    ("ORD-3", "new", date(2025, 6, 1), "1", 43, True, True),
    ("ORD-4", "shipped", date(2025, 7, 9), "2", 43, False, False),
    ("ORD-5", "new", date(2025, 9, 20), "1", 44, False, False),
)

#: (order number, sku, quantity, amount, month of 2025)
_ITEMS = (
    ("ORD-1", "WIDGET", 2, 100, 1),
    ("ORD-1", "GADGET", 1, 70, 1),
    ("ORD-2", "WIDGET", 1, 50, 2),
    ("ORD-3", "GADGET", 1, 30, 4),
    ("ORD-4", "GIZMO", 4, 200, 7),
    ("ORD-5", "GIZMO", 1, 10, 12),
)


async def seed(engine: AsyncEngine) -> None:
    """Create the demo rows once; a populated database is left untouched."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first():
            return
        users = {
            name: User(
                username=name,
                email=f"{name}@example.com",
                password_hash=hash_password(PASSWORD),
                is_superuser=name != "viewer",
            )
            for name in ("alice", "bob", "viewer")
        }
        viewers = Group(name="Viewers")
        session.add_all([*users.values(), viewers])
        session.add_all(
            [
                Supplier(id=42, name="Acme", city="Paris"),
                Supplier(id=43, name="Acme Packaging", city="Lyon"),
                Supplier(id=44, name="Brabant Bakkerij", city="Tilburg"),
            ]
        )
        await session.commit()
        session.add_all(
            [
                Variant(id=1, name="Blue", supplier_id=42),
                Variant(id=2, name="Red", supplier_id=43),
                Product(id=1, name="Widget", supplier_id=42, variant_id=1),
            ]
        )
        orders = {
            number: Order(
                number=number,
                status=status,
                created_on=created_on,
                created_by=owner,
                supplier_id=supplier_id,
                paid=paid,
                locked=locked,
            )
            for number, status, created_on, owner, supplier_id, paid, locked in _ORDERS
        }
        session.add_all(orders.values())
        await session.commit()

        session.add_all(
            OrderItem(
                order_id=orders[number].id,
                sku=sku,
                quantity=quantity,
                amount=amount,
                sold_at=datetime(2025, month, 5, tzinfo=timezone.utc),
            )
            for number, sku, quantity, amount, month in _ITEMS
        )
        session.add(Invoice(number="INV-1", order_id=orders["ORD-1"].id, total=170))
        ids = dict((await session.execute(select(Permission.codename, Permission.id))).all())
        session.add_all(
            GroupPermission(group_id=viewers.id, permission_id=ids[codename])
            for codename in VIEWER_PERMISSIONS
        )
        session.add(UserGroup(user_id=users["viewer"].id, group_id=viewers.id))
        await session.commit()

import argparse
import asyncio
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from io import BytesIO

from faker import Faker
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from examples.erp.accounting.models import Account, AccountType, JournalEntry, JournalLine
from examples.erp.contacts.models import Contact, ContactType
from examples.erp.db import engine
from examples.erp.purchases.models import Bill, BillItem, BillStatus
from examples.erp.sales.models import Invoice, InvoiceItem, InvoiceStatus
from examples.erp.showcase.models import (
    FieldShowcase,
    Priority,
    ProductTag,
    ShowcaseCategory,
    ShowcaseSubcategory,
    showcase_storage,
)
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
    UserPermission,
)
from hyperadmin.loadtest import BulkSeeder
from hyperadmin.loadtest.generators import build_plan
from hyperadmin.management.commands.seed import _to_sync_url

fake = Faker()
logger = logging.getLogger("uvicorn")

# Models a demo visitor may never manage: the built-in users, groups and permissions.
# Everything else registered (every ERP model, including ones added later) is granted.
AUTH_MODELS = (User, Group, Permission, UserGroup, UserPermission, GroupPermission)
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo"  # noqa: S105 - public credentials of the hosted demo

# Public accounts of the hosted demo: (username, password, view_only).
# ``demo`` and ``demo2`` share permissions so two visitors can watch each other's edits
# live; ``demo_ro`` is read-only (only ``view_*`` on non-auth models).
DEMO_ACCOUNTS = (
    (DEMO_USERNAME, DEMO_PASSWORD, False),
    ("demo2", "demo2", False),
    ("demo_ro", "demo_ro", True),
)


async def seed_db():  # noqa: PLR0915
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Check if already seeded
        result = await session.execute(select(Contact))
        if result.first():
            return  # Already seeded

        logger.info("Seeding database with Faker data...")

        # 0. Create superuser
        admin_user = User(
            username="admin",
            email="admin@example.com",
            # A hosted demo sets a secret password so visitors cannot take over the superuser.
            password_hash=hash_password(os.environ.get("HYPERADMIN_ADMIN_PASSWORD", "admin")),
            is_superuser=True,
            first_name="Admin",
            last_name="ERP",
        )
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
        logger.info("  Created 1 superuser (admin)")

        # 1. Accounts
        accounts = [
            Account(code="4000", name="Sales Revenue", account_type=AccountType.REVENUE),
            Account(code="5000", name="Cost of Goods Sold", account_type=AccountType.EXPENSE),
            Account(code="6000", name="Rent Expense", account_type=AccountType.EXPENSE),
            Account(code="6100", name="Software Subscriptions", account_type=AccountType.EXPENSE),
            Account(code="1000", name="Cash", account_type=AccountType.ASSET),
            Account(code="1200", name="Accounts Receivable", account_type=AccountType.ASSET),
            Account(code="2000", name="Accounts Payable", account_type=AccountType.LIABILITY),
            Account(code="3000", name="Owner's Equity", account_type=AccountType.EQUITY),
        ]
        session.add_all(accounts)
        await session.commit()
        for acc in accounts:
            await session.refresh(acc)
        logger.info("  Created %d accounts", len(accounts))

        sales_rev_acc = next(a for a in accounts if a.code == "4000")
        ar_acc = next(a for a in accounts if a.code == "1200")
        sw_exp_acc = next(a for a in accounts if a.code == "6100")
        ap_acc = next(a for a in accounts if a.code == "2000")

        # 2. Contacts (120 total: mix of CUSTOMER, SUPPLIER, BOTH)
        contact_types = (
            [ContactType.CUSTOMER] * 50 + [ContactType.SUPPLIER] * 50 + [ContactType.BOTH] * 20
        )
        random.shuffle(contact_types)
        contacts = [
            Contact(
                name=fake.company(),
                email=fake.company_email(),
                phone=fake.phone_number(),
                address=fake.address(),
                contact_type=contact_types[i],
            )
            for i in range(120)
        ]
        session.add_all(contacts)
        await session.commit()
        for c in contacts:
            await session.refresh(c)

        customers = [
            c for c in contacts if c.contact_type in (ContactType.CUSTOMER, ContactType.BOTH)
        ]
        suppliers = [
            c for c in contacts if c.contact_type in (ContactType.SUPPLIER, ContactType.BOTH)
        ]

        # Fallback: ensure at least some customers and suppliers exist
        if not customers:
            contacts[0].contact_type = ContactType.CUSTOMER
            await session.commit()
            customers = [contacts[0]]
        if not suppliers:
            contacts[-1].contact_type = ContactType.SUPPLIER
            await session.commit()
            suppliers = [contacts[-1]]

        logger.info(
            "  Created %d contacts  (%d customers, %d suppliers, %d both)",
            len(contacts),
            sum(1 for c in contacts if c.contact_type == ContactType.CUSTOMER),
            sum(1 for c in contacts if c.contact_type == ContactType.SUPPLIER),
            sum(1 for c in contacts if c.contact_type == ContactType.BOTH),
        )

        # 3. Invoices (500 total)
        invoice_journal_entries = 0
        for _ in range(500):
            customer = random.choice(customers)  # noqa: S311
            issue_date = fake.date_between(start_date="-1y", end_date="today")
            due_date = issue_date + timedelta(days=30)

            invoice = Invoice(
                number=fake.unique.bothify(text="INV-####-????"),
                date_issued=issue_date,
                date_due=due_date,
                status=random.choice(list(InvoiceStatus)),  # noqa: S311
                customer_id=customer.id,
            )
            session.add(invoice)
            await session.commit()
            await session.refresh(invoice)

            # Items
            total_invoice_amount = 0.0
            for _ in range(random.randint(1, 5)):  # noqa: S311
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=fake.catch_phrase(),
                    quantity=random.randint(1, 10),  # noqa: S311
                    unit_price=round(random.uniform(50.0, 500.0), 2),  # noqa: S311
                )
                session.add(item)
                total_invoice_amount += item.quantity * item.unit_price

            await session.commit()

            # Journal Entry for Invoice
            if invoice.status in (InvoiceStatus.SENT, InvoiceStatus.PAID):
                je = JournalEntry(date_posted=issue_date, description=f"Invoice {invoice.number}")
                session.add(je)
                await session.commit()
                await session.refresh(je)

                # AR Debit, Sales Rev Credit
                jl_debit = JournalLine(
                    entry_id=je.id, account_id=ar_acc.id, debit=total_invoice_amount
                )
                jl_credit = JournalLine(
                    entry_id=je.id, account_id=sales_rev_acc.id, credit=total_invoice_amount
                )
                session.add_all([jl_debit, jl_credit])
                await session.commit()
                invoice_journal_entries += 1

        logger.info("  Created 500 invoices  (%d with journal entries)", invoice_journal_entries)

        # 4. Bills (800 total)
        bill_journal_entries = 0
        for _ in range(800):
            supplier = random.choice(suppliers)  # noqa: S311
            recv_date = fake.date_between(start_date="-1y", end_date="today")
            due_date = recv_date + timedelta(days=15)

            bill = Bill(
                reference=fake.unique.bothify(text="BILL-####-????"),
                date_received=recv_date,
                date_due=due_date,
                status=random.choice(list(BillStatus)),  # noqa: S311
                supplier_id=supplier.id,
            )
            session.add(bill)
            await session.commit()
            await session.refresh(bill)

            # Items
            total_bill_amount = 0.0
            for _ in range(random.randint(1, 3)):  # noqa: S311
                item = BillItem(
                    bill_id=bill.id,
                    description=fake.bs(),
                    quantity=random.randint(1, 5),  # noqa: S311
                    unit_price=round(random.uniform(20.0, 300.0), 2),  # noqa: S311
                )
                session.add(item)
                total_bill_amount += item.quantity * item.unit_price

            await session.commit()

            # Journal Entry for Bill
            if bill.status in (BillStatus.TO_PAY, BillStatus.PAID):
                je = JournalEntry(date_posted=recv_date, description=f"Bill {bill.reference}")
                session.add(je)
                await session.commit()
                await session.refresh(je)

                # Expense Debit, AP Credit
                jl_debit = JournalLine(
                    entry_id=je.id, account_id=sw_exp_acc.id, debit=total_bill_amount
                )
                jl_credit = JournalLine(
                    entry_id=je.id, account_id=ap_acc.id, credit=total_bill_amount
                )
                session.add_all([jl_debit, jl_credit])
                await session.commit()
                bill_journal_entries += 1

        logger.info("  Created 800 bills  (%d with journal entries)", bill_journal_entries)

        # 5. Field showcase (fixed, deterministic rows — demonstrates every widget)
        await _seed_field_showcase(session, suppliers)
        logger.info("  Created field showcase categories, subcategories and items")

        logger.info("Seeding completed.")


def _sample_png_bytes(color: tuple[int, int, int]) -> bytes:
    """A tiny, Pillow-valid PNG generated in-memory (never committed as a binary file)."""
    buf = BytesIO()
    Image.new("RGB", (64, 64), color=color).save(buf, format="PNG")
    return buf.getvalue()


async def _seed_field_showcase(session: AsyncSession, suppliers: list[Contact]) -> None:
    """Seed the widget-showcase models with fixed (non-random) data.

    Deliberately not Faker-driven: these rows exist to let a demo visitor see
    every widget populated and readable, so fixed, descriptive values are
    more useful here than random ones.
    """
    categories = {
        name: ShowcaseCategory(name=name) for name in ("Electronics", "Apparel", "Home & Garden")
    }
    session.add_all(categories.values())
    await session.commit()
    for cat in categories.values():
        await session.refresh(cat)

    subcategory_plan = {
        "Electronics": ["Laptops", "Phones"],
        "Apparel": ["Shirts", "Shoes"],
        "Home & Garden": ["Furniture", "Tools"],
    }
    subcategories: dict[str, ShowcaseSubcategory] = {}
    for cat_name, sub_names in subcategory_plan.items():
        for sub_name in sub_names:
            sub = ShowcaseSubcategory(name=sub_name, category_id=categories[cat_name].id)
            session.add(sub)
            subcategories[sub_name] = sub
    await session.commit()
    for sub in subcategories.values():
        await session.refresh(sub)

    items_plan = [
        {
            "name": 'Ultraslim Laptop 14"',
            "description": "A thin-and-light laptop with a 14-inch display and all-day battery.",
            "quantity_in_stock": 42,
            "unit_price": 1299.00,
            "is_active": True,
            "priority": Priority.HIGH,
            "tags": [ProductTag.NEW, ProductTag.FEATURED],
            "launched_at": datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            "subcategory": "Laptops",
            "color": (66, 135, 245),
        },
        {
            "name": "Flagship Phone X",
            "description": "Our flagship phone with a triple camera and 5G.",
            "quantity_in_stock": 120,
            "unit_price": 899.00,
            "is_active": True,
            "priority": Priority.URGENT,
            "tags": [ProductTag.FEATURED, ProductTag.LIMITED],
            "launched_at": datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc),
            "subcategory": "Phones",
            "color": (245, 101, 66),
        },
        {
            "name": "Classic Crew Shirt",
            "description": "100% cotton crew-neck shirt, available in six colors.",
            "quantity_in_stock": 300,
            "unit_price": 24.99,
            "is_active": True,
            "priority": Priority.LOW,
            "tags": [ProductTag.ON_SALE],
            "launched_at": datetime(2025, 6, 1, 8, 0, tzinfo=timezone.utc),
            "subcategory": "Shirts",
            "color": (66, 245, 155),
        },
        {
            "name": "Trail Running Shoes",
            "description": "Lightweight trail running shoes with reinforced toe caps.",
            "quantity_in_stock": 75,
            "unit_price": 129.50,
            "is_active": True,
            "priority": Priority.MEDIUM,
            "tags": [ProductTag.NEW],
            "launched_at": datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
            "subcategory": "Shoes",
            "color": (245, 221, 66),
        },
        {
            "name": "Oak Dining Table",
            "description": "Solid oak dining table, seats six.",
            "quantity_in_stock": 8,
            "unit_price": 749.00,
            "is_active": False,
            "priority": Priority.LOW,
            "tags": [ProductTag.DISCONTINUED],
            "launched_at": datetime(2023, 9, 10, 14, 0, tzinfo=timezone.utc),
            "subcategory": "Furniture",
            "color": (160, 110, 66),
        },
        {
            "name": "Cordless Drill Set",
            "description": "18V cordless drill with two batteries and a carry case.",
            "quantity_in_stock": 54,
            "unit_price": 89.00,
            "is_active": True,
            "priority": Priority.MEDIUM,
            "tags": [ProductTag.FEATURED, ProductTag.ON_SALE],
            "launched_at": datetime(2026, 2, 11, 16, 45, tzinfo=timezone.utc),
            "subcategory": "Tools",
            "color": (120, 120, 245),
        },
    ]

    for i, plan in enumerate(items_plan):
        slug = plan["subcategory"].lower().replace(" ", "-")
        photo_name = f"showcase-{slug}.png"
        manual_name = f"showcase-{slug}-manual.txt"
        showcase_storage.write(file=BytesIO(_sample_png_bytes(plan["color"])), name=photo_name)
        showcase_storage.write(
            file=BytesIO(
                f"Specification sheet for {plan['name']}.\nGenerated by examples/erp/seed.py.\n".encode()
            ),
            name=manual_name,
        )
        sub = subcategories[plan["subcategory"]]
        supplier = suppliers[i % len(suppliers)] if suppliers else None
        item = FieldShowcase(
            name=plan["name"],
            description=plan["description"],
            quantity_in_stock=plan["quantity_in_stock"],
            unit_price=plan["unit_price"],
            is_active=plan["is_active"],
            priority=plan["priority"],
            tags=plan["tags"],
            launched_at=plan["launched_at"],
            category_id=sub.category_id,
            subcategory_id=sub.id,
            supplier_id=supplier.id if supplier else None,
        )
        session.add(item)
        await session.flush()
        # The files are already in storage, so store their names with a plain UPDATE.
        # Assigning a name string through the FileType/ImageType columns only works on
        # newer fastapi-storages; the oldest supported release expects an upload object.
        await session.execute(
            text(
                f"UPDATE {FieldShowcase.__tablename__} "  # noqa: S608 - fixed table name
                "SET manual_file = :manual, photo = :photo WHERE id = :id"
            ),
            {"manual": manual_name, "photo": photo_name, "id": item.id},
        )
    await session.commit()


async def seed_demo_user() -> None:
    """Create the public accounts of the hosted demo (idempotent).

    None is a superuser: ``demo`` and ``demo2`` hold every synced permission except those
    on the built-in auth models, so visitors can use the whole app but cannot change
    users, groups, permissions or passwords; ``demo_ro`` holds only the ``view_*`` ones.
    Run after permissions are synced.
    """
    auth_names = {model.__name__.lower() for model in AUTH_MODELS}
    async with AsyncSession(engine, expire_on_commit=False) as session:
        permissions = (
            (
                await session.execute(
                    select(Permission).where(Permission.content_type.not_in(auth_names))
                )
            )
            .scalars()
            .all()
        )
        for username, password, view_only in DEMO_ACCOUNTS:
            existing = await session.execute(select(User).where(User.username == username))
            if existing.first():
                continue
            user = User(
                username=username,
                email=f"{username}@example.com",
                password_hash=hash_password(password),
                first_name="Demo",
                last_name="Visitor",
            )
            session.add(user)
            await session.flush()
            granted = [p for p in permissions if not view_only or p.codename.startswith("view_")]
            session.add_all(UserPermission(user_id=user.id, permission_id=p.id) for p in granted)
            await session.commit()
            logger.info(
                "  Created demo user %s with %d ERP permissions",
                username,
                len(granted),
            )


async def bulk_seed_erp(
    count: int,
    *,
    batch_size: int = 5000,
    rng_seed: int = 42,
    database_url: str | None = None,
):
    """Bulk-seed ``count`` synthetic ERP rows via :class:`hyperadmin.loadtest.BulkSeeder`.

    The seeder is synchronous (SQLAlchemy Core ``insert`` is sync), so it runs in a worker
    thread via :func:`asyncio.to_thread` to stay friendly to the example's async event loop.
    Tables are created idempotently first so a fresh database works out of the box.
    """
    sync_url = _to_sync_url(database_url or str(engine.url))
    sync_engine = create_engine(sync_url)
    try:
        SQLModel.metadata.create_all(sync_engine)
        plan = build_plan("erp", seed=rng_seed).scaled(count)
        seeder = BulkSeeder(
            plan=plan,
            engine=sync_engine,
            batch_size=batch_size,
            rng_seed=rng_seed,
            install_signal_handlers=False,
        )
        return await asyncio.to_thread(seeder.run)
    finally:
        sync_engine.dispose()


def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed the ERP example database.")
    parser.add_argument(
        "--bulk", type=int, metavar="N", help="bulk-seed N synthetic rows for load testing"
    )
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.bulk is not None:
        summary = asyncio.run(
            bulk_seed_erp(args.bulk, batch_size=args.batch_size, rng_seed=args.seed)
        )
        logger.info(
            "Bulk-seeded %d rows in %.1fs (%.0f rows/s).",
            summary.rows_inserted,
            summary.elapsed_seconds,
            summary.rows_per_second,
        )
    else:
        asyncio.run(seed_db())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _main()

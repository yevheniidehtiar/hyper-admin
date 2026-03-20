import random
from datetime import timedelta

from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from examples.erp.accounting.models import Account, AccountType, JournalEntry, JournalLine
from examples.erp.contacts.models import Contact, ContactType
from examples.erp.db import engine
from examples.erp.purchases.models import Bill, BillItem, BillStatus
from examples.erp.sales.models import Invoice, InvoiceItem, InvoiceStatus
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User

fake = Faker()


async def seed_db():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Check if already seeded
        result = await session.execute(select(Contact))
        if result.first():
            return  # Already seeded

        print("Seeding database with Faker data...")

        # 0. Create superuser
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("admin"),
            is_superuser=True,
            first_name="Admin",
            last_name="ERP",
        )
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)

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

        sales_rev_acc = next(a for a in accounts if a.code == "4000")
        ar_acc = next(a for a in accounts if a.code == "1200")
        sw_exp_acc = next(a for a in accounts if a.code == "6100")
        ap_acc = next(a for a in accounts if a.code == "2000")

        # 2. Contacts
        contacts = []
        for _ in range(30):
            contacts.append(
                Contact(
                    name=fake.company(),
                    email=fake.company_email(),
                    phone=fake.phone_number(),
                    address=fake.address(),
                    contact_type=random.choice([ContactType.CUSTOMER, ContactType.SUPPLIER]),
                )
            )
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

        # 3. Invoices
        for _ in range(50):
            customer = random.choice(customers)
            issue_date = fake.date_between(start_date="-1y", end_date="today")
            due_date = issue_date + timedelta(days=30)

            invoice = Invoice(
                number=fake.unique.bothify(text="INV-####-????"),
                date_issued=issue_date,
                date_due=due_date,
                status=random.choice(list(InvoiceStatus)),
                customer_id=customer.id,
            )
            session.add(invoice)
            await session.commit()
            await session.refresh(invoice)

            # Items
            total_invoice_amount = 0.0
            for _ in range(random.randint(1, 5)):
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=fake.catch_phrase(),
                    quantity=random.randint(1, 10),
                    unit_price=round(random.uniform(50.0, 500.0), 2),
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

        # 4. Bills
        for _ in range(30):
            supplier = random.choice(suppliers)
            recv_date = fake.date_between(start_date="-1y", end_date="today")
            due_date = recv_date + timedelta(days=15)

            bill = Bill(
                reference=fake.unique.bothify(text="BILL-####-????"),
                date_received=recv_date,
                date_due=due_date,
                status=random.choice(list(BillStatus)),
                supplier_id=supplier.id,
            )
            session.add(bill)
            await session.commit()
            await session.refresh(bill)

            # Items
            total_bill_amount = 0.0
            for _ in range(random.randint(1, 3)):
                item = BillItem(
                    bill_id=bill.id,
                    description=fake.bs(),
                    quantity=random.randint(1, 5),
                    unit_price=round(random.uniform(20.0, 300.0), 2),
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

        print("Seeding completed.")

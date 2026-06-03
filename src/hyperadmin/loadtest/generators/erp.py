"""Hard-coded ERP seed plan.

Mirrors the ``examples/erp`` schema (``erp_*`` tables). The plan order keeps every parent
before its children so the FK pool is populated when a child table starts:

    accounts → contacts → invoices → invoice_items → bills → bill_items
                                              journal_entries → journal_lines

Enum columns are stored as their string *values* (``"Asset"``, ``"Draft"`` …) — the same form
SQLModel persists — so reflected Core inserts accept them directly. ``Faker`` is imported
lazily inside :func:`build_erp_plan` so importing :mod:`hyperadmin.loadtest` never requires it.
"""

from __future__ import annotations

from datetime import timedelta

from hyperadmin.loadtest.plan import SeedPlan, TablePlan

# Enum value pools (the persisted string form, not the member names).
_ACCOUNT_TYPES = ("Asset", "Liability", "Equity", "Revenue", "Expense")
_INVOICE_STATUSES = ("Draft", "Sent", "Paid", "Cancelled")
_BILL_STATUSES = ("Draft", "To Pay", "Paid")

# Probability a journal line is a debit (vs a credit) — a coin flip keeps the ledger balanced.
_DEBIT_PROBABILITY = 0.5

# Relative weights (rescaled to ``--count`` by SeedPlan.scaled). Shapes a realistic ERP mix:
# many line items, fewer documents, a small chart of accounts.
_WEIGHTS = {
    "erp_accounts": 10,
    "erp_contacts": 100,
    "erp_invoices": 1000,
    "erp_invoice_items": 3000,
    "erp_bills": 800,
    "erp_bill_items": 2000,
    "erp_journal_entries": 1500,
    "erp_journal_lines": 3000,
}


def build_erp_plan(*, seed: int = 42) -> SeedPlan:
    """Return the canonical ERP :class:`SeedPlan` with a deterministically seeded Faker."""
    from faker import Faker  # noqa: PLC0415 - dev-only dep, imported when a plan is built

    fake = Faker()
    fake.seed_instance(seed)

    def accounts(pool, rng, seq):  # noqa: ARG001 - factory protocol signature
        return {
            "code": f"ACC-{seq:08d}",
            "name": fake.bs().title(),
            "account_type": rng.choice(_ACCOUNT_TYPES),
        }

    def contacts(pool, rng, seq):  # noqa: ARG001 - factory protocol signature
        return {
            "name": fake.company(),
            "email": f"contact{seq}@{fake.domain_name()}",
            "phone": fake.phone_number()[:20],
            "contact_type": rng.choice(("Customer", "Supplier", "Both")),
        }

    def invoices(pool, rng, seq):
        issued = fake.date_between(start_date="-2y", end_date="today")
        return {
            "number": f"INV-{seq:08d}",
            "date_issued": issued,
            "date_due": issued + timedelta(days=30),
            "status": rng.choice(_INVOICE_STATUSES),
            "customer_id": pool.sample("erp_contacts"),
        }

    def invoice_items(pool, rng, seq):  # noqa: ARG001
        return {
            "invoice_id": pool.sample("erp_invoices"),
            "description": fake.catch_phrase(),
            "quantity": float(rng.randint(1, 10)),
            "unit_price": round(rng.uniform(50.0, 500.0), 2),
        }

    def bills(pool, rng, seq):
        received = fake.date_between(start_date="-2y", end_date="today")
        return {
            "reference": f"BILL-{seq:08d}",
            "date_received": received,
            "date_due": received + timedelta(days=15),
            "status": rng.choice(_BILL_STATUSES),
            "supplier_id": pool.sample("erp_contacts"),
        }

    def bill_items(pool, rng, seq):  # noqa: ARG001
        return {
            "bill_id": pool.sample("erp_bills"),
            "description": fake.bs(),
            "quantity": float(rng.randint(1, 5)),
            "unit_price": round(rng.uniform(20.0, 300.0), 2),
        }

    def journal_entries(pool, rng, seq):  # noqa: ARG001
        return {
            "date_posted": fake.date_between(start_date="-2y", end_date="today"),
            "description": fake.sentence(nb_words=6),
        }

    def journal_lines(pool, rng, seq):  # noqa: ARG001
        debit = round(rng.uniform(0.0, 1000.0), 2) if rng.random() < _DEBIT_PROBABILITY else 0.0
        return {
            "entry_id": pool.sample("erp_journal_entries"),
            "account_id": pool.sample("erp_accounts"),
            "debit": debit,
            "credit": 0.0 if debit else round(rng.uniform(0.0, 1000.0), 2),
        }

    return SeedPlan(
        (
            TablePlan(
                "erp_accounts",
                _WEIGHTS["erp_accounts"],
                accounts,
                ("code", "name", "account_type"),
                unique_columns=("code",),
            ),
            TablePlan(
                "erp_contacts",
                _WEIGHTS["erp_contacts"],
                contacts,
                ("name", "email", "phone", "contact_type"),
            ),
            TablePlan(
                "erp_invoices",
                _WEIGHTS["erp_invoices"],
                invoices,
                ("number", "date_issued", "date_due", "status", "customer_id"),
                fk_parents=("erp_contacts",),
                unique_columns=("number",),
            ),
            TablePlan(
                "erp_invoice_items",
                _WEIGHTS["erp_invoice_items"],
                invoice_items,
                ("invoice_id", "description", "quantity", "unit_price"),
                fk_parents=("erp_invoices",),
            ),
            TablePlan(
                "erp_bills",
                _WEIGHTS["erp_bills"],
                bills,
                ("reference", "date_received", "date_due", "status", "supplier_id"),
                fk_parents=("erp_contacts",),
            ),
            TablePlan(
                "erp_bill_items",
                _WEIGHTS["erp_bill_items"],
                bill_items,
                ("bill_id", "description", "quantity", "unit_price"),
                fk_parents=("erp_bills",),
            ),
            TablePlan(
                "erp_journal_entries",
                _WEIGHTS["erp_journal_entries"],
                journal_entries,
                ("date_posted", "description"),
            ),
            TablePlan(
                "erp_journal_lines",
                _WEIGHTS["erp_journal_lines"],
                journal_lines,
                ("entry_id", "account_id", "debit", "credit"),
                fk_parents=("erp_journal_entries", "erp_accounts"),
            ),
        )
    )


__all__ = ["build_erp_plan"]

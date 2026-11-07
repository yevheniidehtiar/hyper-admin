import enum
from datetime import date, datetime, timezone
from typing import Any

from sqlmodel import Field, Relationship, SQLModel

from examples.erp.contacts.models import Contact
from hyperadmin import gettext_lazy as _


def _to_pay_tone(row: Any) -> tuple[str, str] | str:
    """A bill still to pay past its due date reads "Overdue" (danger tone)."""
    due = row.get("date_due") if row is not None else None
    if isinstance(due, date) and due < datetime.now(tz=timezone.utc).date():
        return (_("Overdue"), "danger")
    return "warning"


class BillStatus(str, enum.Enum):
    DRAFT = "Draft"
    TO_PAY = "To Pay"
    PAID = "Paid"

    # Pill tones in lists (see ``ha_pill``): member name to a tone or a row callable.
    __ha_tones__ = {"DRAFT": "", "TO_PAY": _to_pay_tone, "PAID": "success"}  # noqa: RUF012


class Bill(SQLModel, table=True):
    __tablename__ = "erp_bills"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    reference: str = Field(index=True)
    date_received: date
    date_due: date
    status: BillStatus = Field(default=BillStatus.DRAFT)

    supplier_id: int = Field(foreign_key="erp_contacts.id")
    supplier: Contact = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    items: list["BillItem"] = Relationship(
        back_populates="bill",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )

    @property
    def total_amount(self) -> float:
        return round(sum(item.total_price for item in self.items), 2)

    def __str__(self) -> str:
        return f"Bill {self.reference}"


class BillItem(SQLModel, table=True):
    __tablename__ = "erp_bill_items"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    bill_id: int = Field(foreign_key="erp_bills.id")
    description: str
    quantity: float
    unit_price: float

    bill: Bill = Relationship(back_populates="items")

    @property
    def total_price(self) -> float:
        return round(self.quantity * self.unit_price, 2)

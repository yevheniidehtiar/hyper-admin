import enum
from datetime import date

from sqlmodel import Field, Relationship, SQLModel

from examples.erp.contacts.models import Contact


class BillStatus(str, enum.Enum):
    DRAFT = "Draft"
    TO_PAY = "To Pay"
    PAID = "Paid"


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
        return sum(item.total_price for item in self.items)

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
        return self.quantity * self.unit_price

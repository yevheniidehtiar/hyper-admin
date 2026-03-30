import enum
from datetime import date

from sqlmodel import Field, Relationship, SQLModel

from examples.erp.contacts.models import Contact


class InvoiceStatus(str, enum.Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    PAID = "Paid"
    CANCELLED = "Cancelled"


class Invoice(SQLModel, table=True):
    __tablename__ = "erp_invoices"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(index=True, unique=True)
    date_issued: date
    date_due: date
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT)

    customer_id: int = Field(foreign_key="erp_contacts.id")
    customer: Contact = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    items: list["InvoiceItem"] = Relationship(
        back_populates="invoice",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )

    @property
    def total_amount(self) -> float:
        return sum(item.total_price for item in self.items)

    def __str__(self) -> str:
        return f"Invoice {self.number}"


class InvoiceItem(SQLModel, table=True):
    __tablename__ = "erp_invoice_items"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="erp_invoices.id")
    description: str
    quantity: float
    unit_price: float

    invoice: Invoice = Relationship(back_populates="items")

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price


class TaxRate(SQLModel, table=True):
    __tablename__ = "erp_tax_rates"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    rate: float

    def __str__(self) -> str:
        return self.name

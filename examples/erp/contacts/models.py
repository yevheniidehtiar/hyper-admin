from __future__ import annotations

import enum

from sqlmodel import Field, Relationship, SQLModel


class ContactType(str, enum.Enum):
    CUSTOMER = "Customer"
    SUPPLIER = "Supplier"
    BOTH = "Both"


class Contact(SQLModel, table=True):
    __tablename__ = "erp_contacts"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    contact_type: ContactType = Field(default=ContactType.CUSTOMER)

    addresses: list[Address] = Relationship(
        back_populates="contact",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )

    def __str__(self) -> str:
        return self.name


class Address(SQLModel, table=True):
    __tablename__ = "erp_addresses"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    street: str
    city: str
    state: str | None = Field(default=None)
    country: str
    postal_code: str | None = Field(default=None)

    contact_id: int = Field(foreign_key="erp_contacts.id")
    contact: Contact = Relationship(
        back_populates="addresses",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    def __str__(self) -> str:
        return f"{self.street}, {self.city}, {self.country}"

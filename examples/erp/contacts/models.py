import enum

from sqlmodel import Field, SQLModel


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
    address: str | None = Field(default=None)
    contact_type: ContactType = Field(default=ContactType.CUSTOMER)

    def __str__(self) -> str:
        return self.name

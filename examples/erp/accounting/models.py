import enum
from datetime import date

from sqlmodel import Field, Relationship, SQLModel


class AccountType(str, enum.Enum):
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    REVENUE = "Revenue"
    EXPENSE = "Expense"


class Account(SQLModel, table=True):
    __tablename__ = "erp_accounts"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    account_type: AccountType

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class JournalEntry(SQLModel, table=True):
    __tablename__ = "erp_journal_entries"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    date_posted: date
    description: str

    lines: list["JournalLine"] = Relationship(
        back_populates="entry",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )


class JournalLine(SQLModel, table=True):
    __tablename__ = "erp_journal_lines"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key="erp_journal_entries.id")
    account_id: int = Field(foreign_key="erp_accounts.id")

    debit: float = Field(default=0.0)
    credit: float = Field(default=0.0)

    entry: JournalEntry = Relationship(back_populates="lines")
    account: Account = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

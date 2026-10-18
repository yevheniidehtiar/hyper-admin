"""The host application's own models (``examples/byoa``).

Nothing here knows about HyperAdmin. The keys are deliberately not ``int``:

* ``Account`` — the host's user model, keyed by a ``uuid.UUID``.
* ``Project`` — a ``uuid.UUID`` key generated on insert.
* ``Country`` — a natural ``str`` key (``"NL"``), entered on create.

``Account.password_hash`` is never shown by the admin: a text field whose name
matches ``password|secret|token|hash`` is treated as sensitive.
"""

from __future__ import annotations

import uuid

from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    """A host user. ``get_current_user`` returns one of these."""

    __tablename__ = "byoa_account"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: str = ""
    password_hash: str = ""
    is_superuser: bool = False
    is_staff: bool = False

    def __str__(self) -> str:
        return self.username


class Country(SQLModel, table=True):
    """A country, keyed by its ISO code."""

    __tablename__ = "byoa_country"

    code: str = Field(primary_key=True, max_length=2)
    name: str = Field(min_length=1)

    def __str__(self) -> str:
        return self.name


class Project(SQLModel, table=True):
    """A project, keyed by a generated UUID."""

    __tablename__ = "byoa_project"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(min_length=1)
    country_code: str | None = Field(default=None, foreign_key="byoa_country.code")

    def __str__(self) -> str:
        return self.name


#: Every table the host creates in its own lifespan (or its Alembic migrations).
HOST_TABLES = [Account.__table__, Country.__table__, Project.__table__]  # type: ignore[attr-defined]

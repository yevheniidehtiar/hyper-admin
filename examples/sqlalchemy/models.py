"""Plain SQLAlchemy 2.0 models (``DeclarativeBase``, no SQLModel).

HyperAdmin reads their fields through ``hyperadmin.core.schema_for``, which builds a
Pydantic schema from the mapper. The models cover the column kinds that matter for
that seam: enum, enum through a ``TypeDecorator``, JSON, nullable string, FK, a
``server_default`` timestamp and a sensitive column.
"""

from __future__ import annotations

import enum
from datetime import datetime  # noqa: TC003 (SQLAlchemy resolves Mapped[...] at runtime)
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class Status(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Priority(enum.Enum):
    LOW = "low"
    HIGH = "high"


class PriorityType(TypeDecorator[Priority]):
    """Store a :class:`Priority` as its value string.

    The column's own Python type is ``str``; the ``Mapped[Priority]`` annotation
    on the model is what tells HyperAdmin to render an enum select.
    """

    impl = String(16)
    cache_ok = True

    def process_bind_param(self, value: Priority | None, dialect: Any) -> str | None:  # noqa: ARG002
        return None if value is None else value.value

    def process_result_value(self, value: str | None, dialect: Any) -> Priority | None:  # noqa: ARG002
        return None if value is None else Priority(value)


class Org(Base):
    __tablename__ = "org"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # Sensitive: the name matches HyperAdmin's heuristic, so it is masked and write-only.
    api_token: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    projects: Mapped[list[Project]] = relationship(back_populates="org")

    def __str__(self) -> str:
        return self.name


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    status: Mapped[Status] = mapped_column(SAEnum(Status), default=Status.DRAFT)
    priority: Mapped[Priority] = mapped_column(PriorityType(), default=Priority.LOW)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("org.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    org: Mapped[Org | None] = relationship(back_populates="projects")

    def __str__(self) -> str:
        return self.name

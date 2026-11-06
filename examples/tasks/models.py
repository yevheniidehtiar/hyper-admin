"""The one business model of the example: a report that background tasks build and deliver."""

from __future__ import annotations

import enum
from datetime import datetime  # noqa: TC003 (SQLAlchemy resolves Mapped[...] at runtime)

from sqlalchemy import DateTime, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ReportStatus(enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    READY = "ready"
    DELIVERED = "delivered"


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    status: Mapped[ReportStatus] = mapped_column(SAEnum(ReportStatus), default=ReportStatus.DRAFT)
    row_count: Mapped[int | None] = mapped_column(default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __str__(self) -> str:
        return self.title

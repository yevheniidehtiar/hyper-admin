"""A dimension over an enum column shows the enum's value, not ``Class.MEMBER``.

SQLAlchemy hands an ``Enum`` column back as enum members; ``str()`` of a
``str``-mixin member is ``"TicketState.OPEN"`` on Python 3.11, which then leaked
into the grid's row headers, the chart labels and the exports.
"""

from __future__ import annotations

import enum
from collections.abc import AsyncIterator
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin_reports import Count, Group, ReportView, TimeBucket
from hyperadmin_reports.grid import build_grid

pytestmark = pytest.mark.anyio


class TicketState(str, enum.Enum):
    OPEN = "Open"
    CLOSED = "Closed"


class EnumTicket(SQLModel, table=True):
    __tablename__ = "test_reports_enum_ticket"

    id: int | None = Field(default=None, primary_key=True)
    state: TicketState
    opened_on: date


class TicketsByState(ReportView):
    slug = "tickets-by-state"
    model = EnumTicket
    rows = [Group("state")]
    cols = [TimeBucket("opened_on", period="month")]
    values = [Count()]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all, tables=[EnumTicket.__table__])  # type: ignore[attr-defined]
    async with AsyncSession(engine) as s:
        s.add_all(
            [
                EnumTicket(state=TicketState.OPEN, opened_on=date(2026, 1, 5)),
                EnumTicket(state=TicketState.OPEN, opened_on=date(2026, 1, 9)),
                EnumTicket(state=TicketState.CLOSED, opened_on=date(2026, 2, 1)),
            ]
        )
        await s.commit()
        yield s
    await engine.dispose()


async def test_an_enum_dimension_reads_as_its_value(session: AsyncSession) -> None:
    """
    Scenario: an enum dimension reads as its value
      Given tickets whose state is a str enum (Open, Closed)
      When  a report grouped by state runs and is laid out as a grid
      Then  the row headers are "Closed" and "Open"
      And   the records hold the plain values
    """
    result = await TicketsByState.run(session)
    grid = build_grid(TicketsByState, result)

    assert [row.label for row in grid.rows] == ["Closed", "Open"]
    assert {record["state"] for record in result.records} == {"Open", "Closed"}

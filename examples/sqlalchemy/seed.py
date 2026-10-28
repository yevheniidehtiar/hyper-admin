"""Seed rows so the list pages are not empty on first run."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from examples.sqlalchemy.models import Org, Priority, Project, Status


async def seed(engine: AsyncEngine) -> None:
    """Insert two orgs and three projects when the tables are empty."""
    async with AsyncSession(engine) as session:
        if (await session.execute(select(Org))).first():
            return
        acme = Org(name="Acme", api_token="acme-secret-token")  # noqa: S106
        globex = Org(name="Globex")
        session.add_all([acme, globex])
        await session.flush()
        session.add_all(
            [
                Project(
                    name="Website",
                    note="Public site",
                    status=Status.ACTIVE,
                    priority=Priority.HIGH,
                    payload={"tags": ["web"]},
                    org_id=acme.id,
                ),
                Project(name="Backend", status=Status.DRAFT, org_id=acme.id),
                Project(name="Mobile", status=Status.ARCHIVED, org_id=globex.id),
            ]
        )
        await session.commit()

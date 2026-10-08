"""Column types private to the built-in auth models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from hyperadmin.core.timezones import utc_now

# ``utc_now`` is re-exported so ``auth/models.py`` depends on ``core/`` only through
# this module.
__all__ = ["UTCNaiveDateTime", "utc_now"]


class UTCNaiveDateTime(TypeDecorator[datetime]):
    """Store UTC as a naive ``timestamp``; hand Python code aware UTC values.

    Keeps the ``timestamp without time zone`` DDL of existing ``hyperadmin_*``
    tables (no migration), avoids asyncpg's rejection of aware values bound to
    ``timestamp`` columns, and behaves the same whichever datetime column type the
    installed sqlmodel would otherwise pick.

    - bind: aware values are converted to UTC and made naive; naive values are
      assumed to already be UTC and stored unchanged.
    - result: naive values are tagged UTC; aware values are converted to UTC.
    """

    impl = DateTime(timezone=False)
    cache_ok = True
    hyperadmin_tz_aware = True

    @property
    def python_type(self) -> type[datetime]:
        return datetime

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:  # noqa: ARG002
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: Any | None, dialect: Dialect) -> datetime | None:  # noqa: ARG002
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

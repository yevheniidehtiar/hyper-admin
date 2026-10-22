"""Per-user saved filter sets: the ``hyperadmin_saved_view`` table and its service.

A saved view is a name a user gives to a list querystring (filter library SDD,
``docs/specs/filter-library.md``). Rows are keyed by ``request.state.user_key``
(what both auth modes set, so host users in bridge mode work too) and by the
model slug; names are unique per ``(user_key, model)`` and enforced by the
database as well as by the service, so a collision is a friendly error rather
than a 500.

The table joins the ``hyperadmin_*`` metadata when this module is imported
(``hyperadmin.views.dynamic`` imports it), so ``hyperadmin init-db`` creates it
and Alembic hosts pick it up through ``hyperadmin.auth.metadata()``; the
hand-written operation is in ``docs/guides/existing-app.md`` section 5.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime  # noqa: TC003 - SQLModel resolves the column annotation at runtime
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode

from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, select

from hyperadmin.auth._types import UTCNaiveDateTime
from hyperadmin.core.adapters import open_session, require_engine_or_session_factory
from hyperadmin.core.timezones import utc_now

if TYPE_CHECKING:
    from collections.abc import Iterable
    from contextlib import AbstractAsyncContextManager

    from hyperadmin.core.adapters import AsyncSessionLike, SessionFactory

__all__ = [
    "MAX_NAME_LENGTH",
    "SavedView",
    "SavedViewNameTakenError",
    "SavedViewService",
    "normalize_querystring",
]

MAX_NAME_LENGTH = 255

#: Querystring keys that describe the request, not the filter set, and so are
#: never part of a saved view: the page cursor and the ``?view=`` loader itself.
_TRANSIENT_KEYS = frozenset({"page", "view"})


class SavedView(SQLModel, table=True):
    """One named filter set of one user on one model."""

    __tablename__ = "hyperadmin_saved_view"  # type: ignore[reportIncompatibleVariableOverride]
    __table_args__ = (
        UniqueConstraint("user_key", "model", "name", name="uq_hyperadmin_saved_view_name"),
    )

    id: int | None = Field(default=None, primary_key=True)
    #: ``request.state.user_key`` of the owner (``str`` so host user ids fit).
    user_key: str = Field(index=True, max_length=255)
    #: The model slug of the list the view belongs to (``Order`` -> ``order``).
    model: str = Field(index=True, max_length=255)
    name: str = Field(max_length=MAX_NAME_LENGTH)
    #: The normalized querystring, without a leading ``?`` (see :func:`normalize_querystring`).
    querystring: str = Field(default="")
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)


class SavedViewNameTakenError(ValueError):
    """The user already has a view with this name on this model."""

    def __init__(self, name: str) -> None:
        super().__init__(f"You already have a view called “{name}”. Pick another name.")
        self.name = name


def normalize_querystring(raw: Any) -> str:
    """Canonical querystring of a filter set: no ``?``, no blanks, no page or view key.

    ``raw`` may be a ``?``-prefixed or bare querystring, a Starlette
    ``QueryParams`` (``multi_items``) or any iterable of ``(key, value)``
    pairs. Pairs are sorted so two URLs that differ only in parameter order
    (or in the page they were on) map to the same saved view.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        pairs: Iterable[tuple[str, str]] = parse_qsl(raw.lstrip("?"), keep_blank_values=False)
    elif hasattr(raw, "multi_items"):
        pairs = raw.multi_items()
    elif isinstance(raw, Mapping):
        pairs = raw.items()
    else:
        pairs = raw
    kept = sorted(
        (str(key), str(value))
        for key, value in pairs
        if key not in _TRANSIENT_KEYS and str(value).strip() != ""
    )
    return urlencode(kept)


def _clean_name(name: Any) -> str:
    text = str(name or "").strip()
    if not text:
        msg = "Give the view a name."
        raise ValueError(msg)
    if len(text) > MAX_NAME_LENGTH:
        msg = f"View names are at most {MAX_NAME_LENGTH} characters."
        raise ValueError(msg)
    return text


class SavedViewService:
    """Lists, creates and deletes a user's saved views on one model.

    Every method takes the ``user_key`` explicitly: a view is only ever read,
    written or deleted by its owner, and an id that belongs to someone else is
    indistinguishable from one that does not exist.
    """

    def __init__(
        self, engine: Any = None, *, session_factory: SessionFactory | None = None
    ) -> None:
        require_engine_or_session_factory("SavedViewService", engine, session_factory)
        self.engine = engine
        self.session_factory = session_factory

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        return open_session(self.engine, self.session_factory)

    async def list_for(self, user_key: Any, model: str) -> list[SavedView]:
        """The user's views on ``model``, oldest first."""
        stmt = (
            select(SavedView)
            .where(SavedView.user_key == str(user_key), SavedView.model == model)
            .order_by(SavedView.created_at, SavedView.id)  # type: ignore[arg-type]
        )
        async with self._session() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def get(self, user_key: Any, model: str, view_id: int) -> SavedView | None:
        """The view ``view_id`` when it is the user's own on ``model``, else ``None``."""
        async with self._session() as session:
            return await self._own(session, user_key, model, view_id)

    async def create(self, user_key: Any, model: str, name: Any, querystring: Any) -> SavedView:
        """Save ``querystring`` under ``name`` for the user.

        Raises:
            ValueError: For a blank or over-long name.
            SavedViewNameTakenError: When the user already has a view of that name on ``model``.
        """
        clean = _clean_name(name)
        view = SavedView(
            user_key=str(user_key),
            model=model,
            name=clean,
            querystring=normalize_querystring(querystring),
        )
        async with self._session() as session:
            taken = await session.execute(
                select(SavedView.id).where(
                    SavedView.user_key == view.user_key,
                    SavedView.model == model,
                    SavedView.name == clean,
                )
            )
            if taken.scalar_one_or_none() is not None:
                raise SavedViewNameTakenError(clean)
            session.add(view)
            try:
                await session.commit()
            except IntegrityError as exc:
                # Two saves of the same name raced past the check above: the
                # unique constraint is the authority.
                raise SavedViewNameTakenError(clean) from exc
            await session.refresh(view)
        return view

    async def delete(self, user_key: Any, model: str, view_id: int) -> bool:
        """Delete the user's view ``view_id``; ``False`` when it is not theirs (or gone)."""
        async with self._session() as session:
            view = await self._own(session, user_key, model, view_id)
            if view is None:
                return False
            await session.delete(view)
            await session.commit()
            return True

    @staticmethod
    async def _own(
        session: AsyncSessionLike, user_key: Any, model: str, view_id: int
    ) -> SavedView | None:
        stmt = select(SavedView).where(
            SavedView.id == view_id,
            SavedView.user_key == str(user_key),
            SavedView.model == model,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

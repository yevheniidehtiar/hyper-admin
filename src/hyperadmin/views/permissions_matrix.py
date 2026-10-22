"""The permission-matrix page: grid, diff save, object-rule popover, conflict banner.

``docs/specs/permission-matrix-ui.md``. The page is a built-in
:class:`~hyperadmin.core.plugins.Plugin` that ``Admin`` registers through the
plugin registry when built-in auth models are in use and
``settings.permissions_matrix_enabled`` is on, so its router runs under
``HyperAdminRoute`` (auth bridge, CSRF guard, error pages) and its sidebar
entry and codename are wired like any plugin page's.

Routes (``{prefix}`` is the admin mount path):

* ``GET  {prefix}/permissions-matrix/?group_id=``   grid page (HTMX: the grid block)
* ``POST {prefix}/permissions-matrix/save``         diff save -> 200 / 403 / 404 / 409
* ``GET  {prefix}/permissions-matrix/conflict``     the conflict banner fragment
* ``GET  {prefix}/permissions-matrix/object/{group}/{model}``  object-rule popover
* ``POST {prefix}/permissions-matrix/object/{group}/{model}``  add / remove one rule

Every POST passes the ``HyperAdminRoute`` CSRF guard (the JSON save sends the
``X-CSRF-Token`` header the base layout's ``hx-headers`` carries), so no
per-save token travels in the payload. Save outcomes other than the page-level
403 are *rendered*, not raised: a conflict or a rejected cell must land in the
page's banner slot, not in the error toast ``HyperAdminRoute`` would show.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlmodel import select

from hyperadmin.auth.models import Group
from hyperadmin.core.adapters import open_session
from hyperadmin.permissions import (
    ConflictError,
    GroupNotFoundError,
    ObjectRuleKey,
    ObjectRuleService,
    PermissionMatrixService,
    UnknownPermissionError,
    audit_rows,
    compute_diff,
    object_rule_row,
    write_audit,
)
from hyperadmin.views.htmx import HtmxTemplateResponse

if TYPE_CHECKING:
    from collections.abc import Iterable

    from hyperadmin.core.adapters import AsyncSessionLike
    from hyperadmin.permissions import MatrixGrid

logger = logging.getLogger(__name__)

#: Plugin name and page prefix of the built-in page.
PLUGIN_NAME = "permissions-matrix"
PAGE_PREFIX = "/permissions-matrix"
#: ``HX-Trigger`` value of a committed save (the matrix and the popover both send it).
SAVED_TRIGGER = "permissions-saved"
#: Route names (``hyperadmin:<name>``).
ROUTE_GRID = "permissions-matrix"
ROUTE_SAVE = "permissions-matrix-save"
ROUTE_CONFLICT = "permissions-matrix-conflict"
ROUTE_OBJECT = "permissions-matrix-object"
#: Body of the 409 outcome (the spec's wording; the banner template renders it).
CONFLICT_MESSAGE = "Permissions changed elsewhere — reload"


class ChangeIn(BaseModel):
    """One diff entry of the save envelope."""

    model_config = ConfigDict(extra="forbid")

    model: str
    codename: str
    granted: bool


class SaveEnvelope(BaseModel):
    """``{group_id, version, changes: [...]}`` as the grid posts it (SDD "API")."""

    model_config = ConfigDict(extra="forbid")

    group_id: int
    version: int
    changes: list[ChangeIn] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _SaveRequest:
    """A parsed save: a diff (``submitted``) or a full-grid form post (``checked``)."""

    group_id: int
    version: int
    submitted: dict[str, bool] | None
    checked: frozenset[str]

    def values(self, grid: MatrixGrid) -> dict[str, bool]:
        """``codename -> granted`` for :func:`compute_diff`."""
        if self.submitted is not None:
            return self.submitted
        return {
            cell.codename: cell.codename in self.checked
            for row in grid.rows
            for cell in row.cells.values()
        }


@dataclass(frozen=True, slots=True)
class RejectedCell:
    """A change the operator may not make, with the reason the banner shows."""

    model: str
    codename: str
    reason: str


class PermissionMatrixPage:
    """The built-in ``permissions-matrix`` plugin page."""

    name = PLUGIN_NAME

    def __init__(self, admin: Any) -> None:
        self.admin = admin
        self.codename: str = admin.settings.permissions_matrix_codename
        self.matrix = PermissionMatrixService(admin.engine, session_factory=admin.session_factory)
        self.rules = ObjectRuleService(admin.engine, session_factory=admin.session_factory)
        self._html = HtmxTemplateResponse(admin.templates)

    # -- plugin contract ------------------------------------------------------------

    def on_register(self, admin: Any) -> None:
        """Contribute the page, its sidebar entry and its codename."""
        admin.plugins.add_page(self, self._router(), prefix=PAGE_PREFIX)
        admin.plugins.add_nav_entry(
            self,
            label="Permission matrix",
            url_name=ROUTE_GRID,
            icon="shield-check",
            permission=self.codename,
            section="Access",
        )
        admin.plugins.add_permission(self, self.codename, "Can change group permissions")

    def _router(self) -> APIRouter:
        router = APIRouter()
        page = self

        @router.get("/", name=ROUTE_GRID, response_class=HTMLResponse)
        async def grid(request: Request, group_id: int | None = None) -> Response:
            return await page.grid_view(request, group_id)

        @router.post("/save", name=ROUTE_SAVE, response_class=HTMLResponse)
        async def save(request: Request) -> Response:
            return await page.save_view(request)

        @router.get("/conflict", name=ROUTE_CONFLICT, response_class=HTMLResponse)
        async def conflict(request: Request, group_id: int) -> Response:
            return await page.conflict_view(request, group_id)

        @router.get("/object/{group}/{model}", name=ROUTE_OBJECT, response_class=HTMLResponse)
        async def object_rules(request: Request, group: str, model: str) -> Response:
            return await page.object_view(request, group, model)

        @router.post("/object/{group}/{model}", name=f"{ROUTE_OBJECT}-save")
        async def object_save(request: Request, group: str, model: str) -> Response:
            return await page.object_save_view(request, group, model)

        return router

    # -- access ---------------------------------------------------------------------

    async def _require_access(self, request: Request) -> Any:
        """Return the request's user, or raise 403 when they may not use the matrix."""
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=403, detail="Authentication required")
        checker = self.admin.permission_checker
        if checker is not None and not await checker.has_permission(user, self.codename):
            raise HTTPException(status_code=403, detail="Permission denied")
        return user

    async def _not_grantable(self, user: Any, codenames: Iterable[str]) -> list[str]:
        """The codenames the operator lacks themselves (they may not hand those out)."""
        checker = self.admin.permission_checker
        if checker is None or getattr(user, "is_superuser", False):
            return []
        held = set(await checker.get_user_permissions(user))
        return [codename for codename in codenames if codename not in held]

    @staticmethod
    def _actor_key(request: Request) -> str:
        return str(getattr(request.state, "user_key", ""))

    # -- lookups --------------------------------------------------------------------

    def _session(self) -> Any:
        return open_session(self.admin.engine, self.admin.session_factory)

    async def _groups(self) -> list[dict[str, Any]]:
        async with self._session() as session:
            rows = (await session.execute(select(Group.id, Group.name).order_by(Group.name))).all()
        return [{"id": group_id, "name": name} for group_id, name in rows]

    async def _group_id(self, ref: str) -> int:
        """Resolve a path segment that is a group id or a group name; 404 otherwise."""
        if ref.isdigit():
            return int(ref)
        async with self._session() as session:
            stmt = select(Group.id).where(Group.name == ref)
            group_id = (await session.execute(stmt)).scalar_one_or_none()
        if group_id is None:
            raise HTTPException(status_code=404, detail="Group not found")
        return int(group_id)

    @staticmethod
    def _registered_slugs() -> set[str]:
        from hyperadmin.core.registry import site  # noqa: PLC0415 - registry is filled late

        return {model.__name__.lower() for model in site._registry}

    async def _load_grid_or_404(self, group_id: int) -> MatrixGrid:
        try:
            return await self.matrix.load_grid(group_id)
        except GroupNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Group not found") from exc

    # -- rendering ------------------------------------------------------------------

    def _render(
        self,
        request: Request,
        template: str,
        context: dict[str, Any],
        *,
        block: str | None = None,
        status_code: int = 200,
    ) -> Response:
        context.setdefault("request", request)
        context.setdefault("matrix_codename", self.codename)
        return self._html.render(
            template_name=template,
            context=context,
            request=request,
            block=block,
            status_code=status_code,
        )

    async def _grid_context(self, group_id: int | None) -> dict[str, Any]:
        groups = await self._groups()
        selected = group_id if group_id is not None else (groups[0]["id"] if groups else None)
        context: dict[str, Any] = {
            "groups": groups,
            "selected_group_id": selected,
            "grid": None,
            "rule_counts": {},
            "group_gone": False,
        }
        if selected is None:
            return context
        try:
            context["grid"] = await self.matrix.load_grid(selected)
            context["rule_counts"] = await self.rules.counts_for(selected)
        except GroupNotFoundError:
            context["group_gone"] = True
        return context

    async def grid_view(self, request: Request, group_id: int | None) -> Response:
        """The grid page; an HTMX request (group switch) gets the ``grid`` block only."""
        await self._require_access(request)
        context = await self._grid_context(group_id)
        context["outcome"] = None
        status = 404 if context["group_gone"] else 200
        return self._render(
            request, "permissions/matrix.html", context, block="grid", status_code=status
        )

    async def _outcome(
        self,
        request: Request,
        outcome: str,
        *,
        status_code: int,
        group_id: int | None,
        **extra: Any,
    ) -> Response:
        """Render a save outcome: the banner fragment for HTMX, the whole page otherwise."""
        context: dict[str, Any] = {
            "outcome": outcome,
            "group_id": group_id,
            "conflict_message": CONFLICT_MESSAGE,
            "rejected": [],
            "saved": 0,
            "version": None,
            **extra,
        }
        if request.headers.get("hx-request"):
            return self._render(
                request, "permissions/_banner.html", context, status_code=status_code
            )
        context.update(await self._grid_context(group_id))
        return self._render(request, "permissions/matrix.html", context, status_code=status_code)

    # -- save -----------------------------------------------------------------------

    @staticmethod
    async def _parse_save(request: Request) -> _SaveRequest:
        """Read the JSON diff envelope, or the full-grid form a JavaScript-less page posts."""
        if "application/json" in request.headers.get("content-type", ""):
            try:
                envelope = SaveEnvelope.model_validate(await request.json())
            except (ValidationError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="Invalid save payload") from exc
            submitted = {change.codename: change.granted for change in envelope.changes}
            return _SaveRequest(envelope.group_id, envelope.version, submitted, frozenset())
        form = await request.form()
        try:
            group_id = int(str(form.get("group_id", "")))
            version = int(str(form.get("version", "")))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid save payload") from exc
        checked = frozenset(str(value) for value in form.getlist("perm"))
        return _SaveRequest(group_id, version, None, checked)

    async def save_view(self, request: Request) -> Response:
        """Apply a diff: 200 + ``HX-Trigger`` on success, 403 / 404 / 409 rendered as banners."""
        user = await self._require_access(request)
        parsed = await self._parse_save(request)
        try:
            grid = await self.matrix.load_grid(parsed.group_id)
        except GroupNotFoundError:
            return await self._outcome(
                request, "group_gone", status_code=404, group_id=parsed.group_id
            )
        try:
            changes = compute_diff(grid, parsed.values(grid))
        except UnknownPermissionError as exc:
            detail = f"Unknown permission: {', '.join(exc.codenames)}"
            raise HTTPException(status_code=400, detail=detail) from exc

        wanted = [change.codename for change in changes if change.granted]
        rejected = await self._not_grantable(user, wanted)
        if rejected:
            cells = [
                RejectedCell(
                    model=change.model,
                    codename=change.codename,
                    reason="You can only grant permissions you have yourself",
                )
                for change in changes
                if change.codename in rejected
            ]
            return await self._outcome(
                request, "rejected", status_code=403, group_id=grid.group_id, rejected=cells
            )

        rows = audit_rows(self._actor_key(request), grid.group_id, changes)

        async def stage_audit(session: AsyncSessionLike) -> None:
            await write_audit(session, rows)

        try:
            version = await self.matrix.save_diff(
                grid.group_id, parsed.version, changes, before_commit=stage_audit
            )
        except ConflictError:
            return await self._outcome(request, "conflict", status_code=409, group_id=grid.group_id)
        except GroupNotFoundError:
            return await self._outcome(
                request, "group_gone", status_code=404, group_id=grid.group_id
            )
        except UnknownPermissionError as exc:
            detail = f"Unknown permission: {', '.join(exc.codenames)}"
            raise HTTPException(status_code=400, detail=detail) from exc
        except Exception:
            logger.exception("permission matrix save failed for group %s", grid.group_id)
            return await self._outcome(request, "failed", status_code=500, group_id=grid.group_id)
        response = await self._outcome(
            request,
            "saved",
            status_code=200,
            group_id=grid.group_id,
            saved=len(changes),
            version=version,
        )
        response.headers["HX-Trigger"] = SAVED_TRIGGER
        return response

    async def conflict_view(self, request: Request, group_id: int) -> Response:
        """The conflict banner on its own (the page fetches it to offer a reload)."""
        await self._require_access(request)
        context = {
            "outcome": "conflict",
            "group_id": group_id,
            "conflict_message": CONFLICT_MESSAGE,
            "rejected": [],
            "saved": 0,
            "version": None,
        }
        return self._render(request, "permissions/_banner.html", context)

    # -- object rules ---------------------------------------------------------------

    async def _object_context(self, group: str, model: str) -> dict[str, Any]:
        group_id = await self._group_id(group)
        slug = model.lower()
        if slug not in self._registered_slugs():
            raise HTTPException(status_code=404, detail="Model not registered")
        grid = await self._load_grid_or_404(group_id)
        row = next(row for row in grid.rows if row.model == slug)
        return {
            "group_id": group_id,
            "group_name": grid.group_name,
            "model": slug,
            "codenames": [cell.codename for cell in row.cells.values()],
            "rules": await self.rules.rules_for(group_id, slug),
            "outcome": None,
            "object_pk": None,
            "codename": None,
        }

    async def object_view(self, request: Request, group: str, model: str) -> Response:
        """The popover fragment listing the group's rules on ``model``."""
        await self._require_access(request)
        context = await self._object_context(group, model)
        return self._render(request, "permissions/object_popover.html", context)

    async def object_save_view(self, request: Request, group: str, model: str) -> Response:
        """Add (``op=add``) or remove (``op=remove``) one rule; idempotent."""
        user = await self._require_access(request)
        context = await self._object_context(group, model)
        form = await request.form()
        op = str(form.get("op", "add"))
        codename = str(form.get("codename", ""))
        object_pk = str(form.get("object_pk", "")).strip()
        if op not in {"add", "remove"} or codename not in context["codenames"] or not object_pk:
            raise HTTPException(status_code=400, detail="Invalid object rule")
        key = ObjectRuleKey(model=context["model"], codename=codename, object_pk=object_pk)
        context["object_pk"] = object_pk
        context["codename"] = codename
        if op == "add" and await self._not_grantable(user, [codename]):
            context["outcome"] = "rejected"
            return self._render(
                request, "permissions/object_popover.html", context, status_code=403
            )
        audit = object_rule_row(
            self._actor_key(request),
            context["group_id"],
            model=key.model,
            codename=codename,
            object_pk=object_pk,
            added=op == "add",
        )
        if op == "add":
            written = await self.rules.add(context["group_id"], key, audit=audit)
        else:
            written = await self.rules.remove(context["group_id"], key, audit=audit)
        context["outcome"] = {"add": "added", "remove": "removed"}[op] if written else "unchanged"
        context["rules"] = await self.rules.rules_for(context["group_id"], key.model)
        response = self._render(request, "permissions/object_popover.html", context)
        if written:
            response.headers["HX-Trigger"] = SAVED_TRIGGER
        return response

"""Pinned sidebar pages: per-request loading and the ``{prefix}/nav/pins`` endpoints.

Spec: ``docs/specs/navigation-and-list-ux.md`` (story st-v059-nav-03). The admin
builds one :class:`NavPins` when auth is configured (pins need a ``user_key``)
and

- adds :meth:`NavPins.load` as a dependency of the admin router, so full-page
  requests carry the user's pin keys in ``request.state.nav_pins`` for the
  sidebar (``nav_pinned_items()``);
- registers :meth:`NavPins.register` 's two routes, which return the re-rendered
  Pinned group (``components/nav_pinned.html``) for HTMX to swap in.

A missing ``hyperadmin_nav_pin`` table is logged once and hides the feature;
it never breaks a page.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Form, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from hyperadmin.core.navigation import find_nav_item, with_legacy_items
from hyperadmin.i18n import gettext
from hyperadmin.navigation.pins import NavPinService, PinLimitError
from hyperadmin.views.navigation import request_nav_tree

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter
    from fastapi.templating import Jinja2Templates
    from starlette.responses import Response

    from hyperadmin.core.navigation import NavItem

__all__ = ["NavPins"]

logger = logging.getLogger(__name__)


class NavPins:
    """The pins feature of one admin."""

    def __init__(self, service: NavPinService, templates: Jinja2Templates) -> None:
        self.service = service
        self.templates = templates
        self._warned = False

    def _unavailable(self, exc: SQLAlchemyError) -> None:
        """Log, once per admin, that the pins table cannot be used."""
        if not self._warned:
            self._warned = True
            logger.warning(
                "Sidebar pins are unavailable; create the hyperadmin_nav_pin table "
                "(hyperadmin init-db, or the existing-app guide, section 5): %s",
                exc,
            )

    async def load(self, request: Request) -> None:
        """Router dependency: put the user's pin keys on ``request.state.nav_pins``.

        Only for requests that render a full page (``GET``, not an HTMX
        partial), so fragments and form posts cost no query.
        """
        user_key = getattr(request.state, "user_key", None)
        if user_key is None or request.method != "GET":
            return
        if request.headers.get("hx-request") and not request.headers.get("hx-boosted"):
            return
        try:
            request.state.nav_pins = await self.service.list_for(user_key)
        except SQLAlchemyError as exc:
            self._unavailable(exc)

    def register(self, router: APIRouter) -> None:
        """Add ``POST /nav/pins`` and ``DELETE /nav/pins/{target}`` to ``router``."""
        router.add_api_route(
            "/nav/pins", self.pin, methods=["POST"], name="admin-nav-pin", include_in_schema=False
        )
        router.add_api_route(
            "/nav/pins/{target}",
            self.unpin,
            methods=["DELETE"],
            name="admin-nav-unpin",
            include_in_schema=False,
        )

    def _item(self, request: Request, target: str) -> NavItem:
        """The visible nav item ``target`` names; 404 when it is unknown or forbidden."""
        item = find_nav_item(request_nav_tree(request, self.templates.env.globals), target)
        if item is None:
            raise HTTPException(status_code=404, detail=gettext("Page not found"))
        return item

    def _known(self) -> set[str]:
        """Every pin key in the nav tree, visible to this user or not."""
        env_globals: Mapping[str, Any] = self.templates.env.globals
        tree = with_legacy_items(
            tuple(env_globals.get("nav_tree") or ()), env_globals.get("nav_items") or ()
        )
        return {item.key for group in tree for item in group.items}

    @staticmethod
    def _user(request: Request) -> Any:
        user_key = getattr(request.state, "user_key", None)
        if user_key is None:
            raise HTTPException(status_code=403, detail="Pins need a signed-in user")
        return user_key

    async def pin(self, request: Request, target: Annotated[str, Form()] = "") -> Response:
        """``POST /nav/pins`` with form ``target=<NavItem.key>``: pin it (idempotent).

        404 for a target the user may not see, 409 (an error toast) past
        ``nav_pins_max``.
        """
        user_key = self._user(request)
        item = self._item(request, target)
        try:
            await self.service.pin(user_key, item.key, known=self._known())
        except PinLimitError as exc:
            raise HTTPException(
                status_code=409,
                detail=gettext("You can pin up to %(count)s pages") % {"count": exc.limit},
            ) from exc
        except SQLAlchemyError as exc:
            self._unavailable(exc)
            raise HTTPException(status_code=404, detail=gettext("Page not found")) from exc
        return await self._fragment(request, user_key, item)

    async def unpin(self, request: Request, target: str) -> Response:
        """``DELETE /nav/pins/{target}``: remove the pin (idempotent); 404 as for ``pin``."""
        user_key = self._user(request)
        item = self._item(request, target)
        try:
            await self.service.unpin(user_key, item.key, known=self._known())
        except SQLAlchemyError as exc:
            self._unavailable(exc)
            raise HTTPException(status_code=404, detail=gettext("Page not found")) from exc
        return await self._fragment(request, user_key, item)

    async def _fragment(self, request: Request, user_key: Any, item: NavItem) -> Response:
        """The re-rendered Pinned group, plus the toggled item's button out of band."""
        request.state.nav_pins = await self.service.list_for(user_key)
        return self.templates.TemplateResponse(
            request, "components/nav_pinned.html", {"request": request, "toggled": item}
        )

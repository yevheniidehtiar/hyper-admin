"""A tiny test-only plugin exercising every plugin-registry seam (SDD phase 1b).

It contributes a page (``GET {prefix}/demo/`` named ``demo-index`` and
``POST {prefix}/demo/ping``), a sidebar entry gated on ``view_demo_report``,
a template dir, a static dir and the ``view_demo_report`` permission. The page
enforces the codename through the admin's own permission checker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

DEMO_PERMISSION = "view_demo_report"
_HERE = Path(__file__).parent


class DemoPlugin:
    """The ``demo`` plugin."""

    name = "demo"

    def __init__(self) -> None:
        self.admin: Any = None

    async def _require_permission(self, request: Request) -> None:
        user = getattr(request.state, "user", None)
        checker = self.admin.permission_checker
        if (
            user is not None
            and checker is not None
            and not await checker.has_permission(user, DEMO_PERMISSION)
        ):
            raise HTTPException(status_code=403, detail="Permission denied")

    def _router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/", name="demo-index", response_class=HTMLResponse)
        async def index(request: Request) -> HTMLResponse:
            await self._require_permission(request)
            return self.admin.templates.TemplateResponse(request, "demo/index.html", {})

        @router.post("/ping", name="demo-ping")
        async def ping(request: Request) -> dict[str, str]:
            await self._require_permission(request)
            return {"pong": self.name}

        return router

    def on_register(self, admin: Any) -> None:
        self.admin = admin
        admin.plugins.add_page(self, self._router())
        admin.plugins.add_nav_entry(
            self,
            label="Demo report",
            url_name="demo-index",
            icon="file-text",
            permission=DEMO_PERMISSION,
            section="Reports",
        )
        admin.plugins.add_template_dir(self, _HERE / "templates")
        admin.plugins.set_static_dir(self, _HERE / "static")
        admin.plugins.add_permission(self, DEMO_PERMISSION)

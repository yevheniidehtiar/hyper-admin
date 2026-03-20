"""Login and logout view handlers for HyperAdmin."""

from __future__ import annotations

from typing import Any

from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import RedirectResponse


async def login_view(
    request: Request,
    templates: Jinja2Templates,
    auth_backend: Any,
    admin_prefix: str,
) -> Any:
    """Handle GET (render form) and POST (authenticate) for login."""
    error = None

    if request.method == "POST":
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        user = await auth_backend.authenticate(str(username), str(password))
        if user is not None:
            await auth_backend.login(request, user)
            return RedirectResponse(url=f"{admin_prefix}/", status_code=302)
        error = "Invalid username or password."

    context = {"request": request, "error": error, "admin_prefix": admin_prefix}
    return templates.TemplateResponse(request, "login.html", context)


async def logout_view(
    request: Request,
    auth_backend: Any,
    admin_prefix: str,
) -> RedirectResponse:
    """Handle POST logout — clear session and redirect to login."""
    await auth_backend.logout(request)
    return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)

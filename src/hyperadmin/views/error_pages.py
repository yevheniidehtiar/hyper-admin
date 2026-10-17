"""HTML error responses for admin routes (403, 404, 409 inside the admin layout).

FastAPI answers an ``HTTPException`` with JSON. That is right for API callers, but
a person who clicks a sidebar link they may not use, or a delete that is refused,
should stay in the admin: a full page in the admin layout for a navigation, a
toast for an HTMX request. The admin route class (``views/route.py``, not an
app-wide exception handler) keeps this to the admin's own routes, so the host
app's error handling is never replaced.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from starlette.exceptions import HTTPException
    from starlette.requests import Request
    from starlette.responses import Response

#: Statuses rendered as HTML for people; others keep FastAPI's JSON response.
HTML_ERROR_STATUSES = frozenset({403, 404, 409})

#: CSS selector of the toast region in ``_messages.html`` (HTMX errors land there).
TOAST_TARGET = ".ha-toast-container"


def wants_html(request: Request) -> bool:
    """Return whether the caller is a browser or HTMX, not a JSON API client."""
    if request.headers.get("hx-request"):
        return True
    return "text/html" in request.headers.get("accept", "")


def render_error(templates: Jinja2Templates, request: Request, exc: HTTPException) -> Response:
    """Render ``exc`` as an admin page, or as a toast fragment for HTMX requests."""
    context = {"request": request, "status_code": exc.status_code, "detail": exc.detail}
    if request.headers.get("hx-request"):
        response = templates.TemplateResponse(
            request, "components/error_toast.html", context, status_code=exc.status_code
        )
        # Show the message as a toast on the current page instead of the request's target.
        response.headers["HX-Retarget"] = TOAST_TARGET
        response.headers["HX-Reswap"] = "beforeend"
        return response
    return templates.TemplateResponse(request, "error.html", context, status_code=exc.status_code)

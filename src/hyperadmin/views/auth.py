from fastapi import Request
from starlette.responses import RedirectResponse


async def logout_view(request: Request):
    """Clears the session and redirects to the login page."""
    request.session.clear()
    admin_prefix = request.app.state.admin_prefix
    return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from hyperadmin.auth.models import User


async def require_authenticated_user(request: Request) -> User:
    """Dependency that ensures a user is logged in.

    Returns the authenticated User object if found in session and database,
    otherwise redirects to the login page.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        admin_prefix = request.app.state.admin_prefix
        raise HTTPException(
            status_code=302,
            headers={"Location": f"{admin_prefix}/login"},
        )

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from hyperadmin.auth.models import UserPermissions

    engine = request.app.state.admin_engine
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.user_permissions).selectinload(UserPermissions.permission))
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            admin_prefix = request.app.state.admin_prefix
            raise HTTPException(
                status_code=302,
                headers={"Location": f"{admin_prefix}/login"},
            )
        # Store for template access and sub-dependencies
        request.state.user = user
        return user

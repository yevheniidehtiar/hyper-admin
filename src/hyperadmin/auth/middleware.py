from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel.sql.expression import select

from hyperadmin.core.registry import site


async def get_current_user(request: Request, session: Any = None) -> Any | None:
    """Dependency to get the currently authenticated user."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    # Find the User model in the registry
    user_model = None
    for model in site.get_registered_models():
        if model.__name__ == "User":
            user_model = model
            break

    if not user_model:
        return None

    # Fetch the user using the provided session
    if session:
        statement = select(user_model).where(user_model.id == user_id)
        results = await session.execute(statement)
        return results.scalar_one_or_none()

    # Fallback to creating a session from the engine if not provided

    # Try to find the router in template globals
    # This is a bit of a hack but avoids passing engine everywhere for now
    # Ideally it should be in request.app.state

    # Actually, we can just use the site registry to find the admin class
    # and use its adapter if we had the engine.

    # Let's try to get it from request.app.state if it was put there
    if hasattr(request.app.state, "hyperadmin_admin"):
        admin = request.app.state.hyperadmin_admin
        async with AsyncSession(admin.engine) as session:
            statement = select(user_model).where(user_model.id == user_id)
            results = await session.execute(statement)
            return results.scalar_one_or_none()

    return None

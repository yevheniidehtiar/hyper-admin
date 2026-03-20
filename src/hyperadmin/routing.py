"""This module will contain the dynamic routing engine for HyperAdmin."""

from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select
from starlette.responses import RedirectResponse

from hyperadmin.auth.backend import verify_password
from hyperadmin.auth.middleware import get_current_user
from hyperadmin.core.options import AdminOptions
from hyperadmin.views.dynamic import DynamicModelView


def _extract_column_names(raw: list[Any] | None, model: type | None = None) -> list[str] | None:
    """Extract field name strings from a list of SQLAlchemy column attributes or properties."""
    if not raw:
        return None
    names: list[str] = []
    for col in raw:
        if hasattr(col, "key"):
            names.append(col.key)
        elif isinstance(col, property) and model:
            # Resolve @property descriptors by scanning the model's MRO
            resolved = False
            for cls in model.__mro__:
                for attr_name, attr_val in vars(cls).items():
                    if attr_val is col:
                        names.append(attr_name)
                        resolved = True
                        break
                if resolved:
                    break
            if not resolved:
                names.append(str(col))
        elif isinstance(col, str):
            names.append(col)
        else:
            names.append(str(col))
    return names


async def require_admin_user(request: Request, user: Any = Depends(get_current_user)):
    """Dependency that ensures a user is authenticated."""
    if not user:
        login_url = request.url_for("admin-login")
        raise HTTPException(
            status_code=303,
            headers={"Location": str(login_url)},
        )
    return user


def create_auth_router(templates: Jinja2Templates, engine: Any) -> APIRouter:
    """Creates an APIRouter for authentication (login/logout)."""
    router = APIRouter()

    @router.get("/login", name="admin-login")
    async def login_page(request: Request):
        return templates.TemplateResponse("auth/login.html", {"request": request})

    @router.post("/login", name="admin-login")
    async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        from hyperadmin.core.registry import site

        # Find the User model in the registry
        user_model = None
        for model in site.get_registered_models():
            if model.__name__ == "User":
                user_model = model
                break

        if not user_model:
            return templates.TemplateResponse(
                "auth/login.html",
                {"request": request, "error": "Authentication system not configured."},
            )

        async with AsyncSession(engine) as session:
            statement = select(user_model).where(user_model.username == username)
            results = await session.execute(statement)
            user = results.scalar_one_or_none()

            if user and verify_password(password, user.password_hash):
                request.session["user_id"] = user.id
                return RedirectResponse(
                    url=str(request.url_for("admin-dashboard")), status_code=303
                )

        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid username or password."},
        )

    @router.get("/logout", name="admin-logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url=str(request.url_for("admin-login")), status_code=303)

    return router


def create_admin_router(  # noqa: PLR0913
    model: type[SQLModel],
    admin_class: Any,
    admin_instance: Any,
    options: AdminOptions,
    engine: Any,
    templates: Jinja2Templates,
    form_include: list[str] | None = None,
    form_create_exclude: list[str] | None = None,
    column_list: list[str] | None = None,
) -> APIRouter:
    """Creates an APIRouter for a given model with the specified admin options."""
    router = APIRouter(dependencies=[Depends(require_admin_user)])
    view = DynamicModelView(
        adapter=admin_instance.adapter_class(model, engine=engine),
        options=options,
        templates=templates,
        app_label=admin_class.app_label,
        form_include=form_include,
        form_create_exclude=form_create_exclude,
        column_list=column_list,
    )
    model_name = model.__name__.lower()

    prefix = f"/{model_name}"

    if options.can_list:
        router.add_api_route(
            prefix,
            view.list_view,
            methods=["GET"],
            name=f"{model_name}-list",
        )

    if options.can_create:
        router.add_api_route(
            prefix,
            view.create_view,
            methods=["POST"],
            name=f"{model_name}-create",
        )
        router.add_api_route(
            f"{prefix}/create",
            view.create_form_view,
            methods=["GET"],
            name=f"{model_name}-create-form",
        )

    if options.can_detail:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            view.detail_view,
            methods=["GET"],
            name=f"{model_name}-detail",
        )

    if options.can_edit:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            view.update_view,
            methods=["PUT"],
            name=f"{model_name}-update",
        )
        router.add_api_route(
            f"{prefix}/{{item_id:int}}/edit",
            view.update_form_view,
            methods=["GET"],
            name=f"{model_name}-update-form",
        )

    if options.can_delete:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            view.delete_action,
            methods=["DELETE"],
            name=f"{model_name}-delete",
        )

    return router


class HyperAdminRouter:
    """Generates and owns all FastAPI routers for HyperAdmin.

    Called internally by ``Admin.mount()``. Iterates ``SiteRegistry`` and
    calls ``create_admin_router`` for each registered model.

    Args:
        engine: The async SQLAlchemy engine passed to every adapter.
        templates: The shared ``Jinja2Templates`` instance used across all views.
    """

    def __init__(self, engine: Any, templates: Jinja2Templates):
        self.engine = engine
        # Enable global whitespace trimming
        templates.env.trim_blocks = True
        templates.env.lstrip_blocks = True
        self.templates = templates
        self.routers: list[APIRouter] = []

    def generate_routes(self) -> None:
        """Generates the routes for the registered models."""
        from hyperadmin.core.registry import site

        # Inject this router into the request scope for dependencies
        async def inject_router_middleware(request: Request, call_next):
            request.scope["hyperadmin_router"] = self
            return await call_next(request)

        # We can't easily add middleware to APIRouter, but we can use request.app
        # However, generate_routes is called during mount.
        # Let's try another approach: put it in the globals of templates
        self.templates.env.globals["hyperadmin_router"] = self

        self.routers = []
        nav_items: list[dict[str, str]] = []

        # Add the authentication router
        auth_router = create_auth_router(self.templates, self.engine)
        self.routers.append(auth_router)

        # Add the main admin dashboard route
        dashboard_router = APIRouter(dependencies=[Depends(require_admin_user)])
        dashboard_router.add_api_route(
            "/",
            self.get_admin_dashboard_view(),
            methods=["GET"],
            name="admin-dashboard",
        )
        self.routers.append(dashboard_router)

        for model, admin_class in site._registry.items():
            admin_instance = admin_class(model)
            # Prioritize options set on admin_class, then fall back to defaults
            options = getattr(admin_class, "options", None) or AdminOptions()
            # If admin_class has list_filter set directly (legacy or class-style)
            if hasattr(admin_class, "list_filter") and not options.list_filter:
                options.list_filter = admin_class.list_filter

            form_include = _extract_column_names(getattr(admin_class, "form_columns", None), model)
            form_create_exclude = _extract_column_names(
                getattr(admin_class, "form_create_exclude", None), model
            )
            column_list = _extract_column_names(
                getattr(admin_class, "column_list", None) or getattr(admin_class, "list", None),
                model,
            )

            router = create_admin_router(
                model=model,
                admin_class=admin_class,
                admin_instance=admin_instance,
                options=options,
                engine=self.engine,
                templates=self.templates,
                form_include=form_include,
                form_create_exclude=form_create_exclude,
                column_list=column_list,
            )
            self.routers.append(router)

            model_name = model.__name__
            nav_items.append(
                {
                    "name": getattr(admin_class, "name_plural", None)
                    or getattr(admin_class, "name", model_name) + "s",
                    "url": f"/{model_name.lower()}",
                    "icon": getattr(admin_class, "icon", ""),
                }
            )

        self.templates.env.globals["nav_items"] = nav_items

    def get_admin_dashboard_view(self):
        from hyperadmin.views.dynamic import admin_dashboard

        async def admin_dashboard_view(request: Request):
            return await admin_dashboard(request, self.templates)

        return admin_dashboard_view

    def get_routers(self) -> list[APIRouter]:
        """Returns the list of generated APIRouters."""
        return self.routers

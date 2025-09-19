import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, select

from hyperadmin.db import get_session

# The templates are now in src/hyperadmin/templates
template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)


def get_error_messages(exc: ValidationError) -> dict[str, Any]:
    """Extracts error messages from a Pydantic ValidationError."""
    errors: dict[str, Any] = {}
    for error in exc.errors():
        if error["loc"]:
            field = error["loc"][0]
            errors[field] = error["msg"]
    return errors


class ModelView:
    """
    A view class for a SQLModel model. This is a base class that should be subclassed.
    The subclass should define the `model` attribute.
    """

    model: type[SQLModel]

    def __init__(self):
        if not hasattr(self, "model"):
            raise ValueError("ModelView subclass must define a 'model' attribute.")
        self.router = APIRouter()
        self.add_routes()

    def add_routes(self):
        """Adds the list, detail, and create view routes to the router."""
        self.router.add_api_route(
            "/",
            self.list_view,
            methods=["GET"],
            name=f"{self.model.__name__.lower()}-list",
        )
        self.router.add_api_route(
            "/create",
            self.create_view,
            methods=["GET", "POST"],
            name=f"{self.model.__name__.lower()}-create",
        )
        self.router.add_api_route(
            "/{item_id}",
            self.detail_view,
            methods=["GET"],
            name=f"{self.model.__name__.lower()}-detail",
        )
        self.router.add_api_route(
            "/{item_id}/update",
            self.update_view,
            methods=["GET", "POST"],
            name=f"{self.model.__name__.lower()}-update",
        )
        self.router.add_api_route(
            "/{item_id}/delete",
            self.delete_action,
            methods=["POST"],
            name=f"{self.model.__name__.lower()}-delete",
        )

    async def delete_action(self, item_id: int, session: Session = Depends(get_session)):
        """Deletes an item."""
        item = session.get(self.model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        session.delete(item)
        session.commit()

        # HTMX will expect an empty response to remove the element
        return {}

    async def update_view(
        self, request: Request, item_id: int, session: Session = Depends(get_session)
    ):
        """Renders the update view and handles form submission for updating an item."""
        item = session.get(self.model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        form_fields = (
            [column.name for column in self.form_columns]
            if hasattr(self, "form_columns")
            else list(self.model.model_fields.keys())
        )
        print(f"Form fields: {form_fields}")

        if request.method == "POST":
            form_data = await request.form()
            try:
                for key, value in form_data.items():
                    setattr(item, key, value)
                session.add(item)
                session.commit()
                session.refresh(item)
                return Response(
                    headers={
                        "HX-Redirect": str(
                            request.url_for(
                                f"{self.model.__name__.lower()}-detail", item_id=item.id
                            )
                        )
                    }
                )
            except ValidationError as e:
                context = {
                    "request": request,
                    "model_name": self.model.__name__,
                    "item": item,
                    "fields": form_fields,
                    "errors": get_error_messages(e),
                }
                return templates.TemplateResponse(request, "update.html", context)

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item": item,
            "fields": form_fields,
            "errors": None,
        }
        return templates.TemplateResponse(request, "update.html", context)

    async def create_view(self, request: Request, session: Session = Depends(get_session)):
        """Renders the create view and handles form submission for creating a new item."""
        form_fields = (
            [column.name for column in self.form_columns]
            if hasattr(self, "form_columns")
            else list(self.model.model_fields.keys())
        )

        if request.method == "POST":
            form_data = await request.form()
            try:
                item = self.model(**form_data)
                session.add(item)
                session.commit()
                session.refresh(item)
                return Response(
                    headers={
                        "HX-Redirect": str(
                            request.url_for(
                                f"{self.model.__name__.lower()}-detail", item_id=item.id
                            )
                        )
                    }
                )
            except ValidationError as e:
                context = {
                    "request": request,
                    "model_name": self.model.__name__,
                    "fields": form_fields,
                    "item": self.model(**form_data),  # Preserve entered data
                    "errors": get_error_messages(e),
                }
                return templates.TemplateResponse(
                    request,
                    "partials/_form.html",
                    context,
                )

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": form_fields,
            "item": self.model(),  # Empty item for the form
            "errors": None,
        }
        return templates.TemplateResponse(request, "create.html", context)

    async def list_view(self, request: Request, session: Session = Depends(get_session)):
        """Renders the list view for the model."""
        items = session.exec(select(self.model)).all()
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
            "items": items,
        }
        return templates.TemplateResponse(request, "list.html", context)

    async def detail_view(
        self, request: Request, item_id: int, session: Session = Depends(get_session)
    ):
        """
        Renders the detail view for a single item.
        Assumes the model has an 'id' field.
        """
        item = session.get(self.model, item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        context = {
            "item_name": f"{self.model.__name__} #{getattr(item, 'id', 'N/A')}",
            "item": item.model_dump(),
        }
        return templates.TemplateResponse(request, "detail.html", context)

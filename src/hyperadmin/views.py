import os
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session, SQLModel

# The templates are now in src/hyperadmin/templates
template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)


class ModelView:
    """
    A view class for a SQLModel model. This is a base class that should be subclassed.
    The subclass should define the `model` attribute.
    """

    model: type[SQLModel]

    def __init__(self, engine):
        if not hasattr(self, "model"):
            raise ValueError("ModelView subclass must define a 'model' attribute.")
        self.engine = engine
        self.router = APIRouter()
        self.add_routes()

    def get_session(self):
        """
        Returns a new database session.
        """
        with Session(self.engine) as session:
            yield session

    def add_routes(self):
        """
        Adds the list, detail, and create view routes to the router.
        """
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}",
            self.list_view,
            methods=["GET"],
            name=f"{self.model.__name__.lower()}-list",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/create",
            self.create_view,
            methods=["GET", "POST"],
            name=f"{self.model.__name__.lower()}-create",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/{{item_id}}",
            self.detail_view,
            methods=["GET"],
            name=f"{self.model.__name__.lower()}-detail",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/{{item_id}}/update",
            self.update_view,
            methods=["GET", "POST"],
            name=f"{self.model.__name__.lower()}-update",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/{{item_id}}/delete",
            self.delete_action,
            methods=["POST"],
            name=f"{self.model.__name__.lower()}-delete",
        )

    async def delete_action(self, item_id: int, session: Session = Depends(self.get_session)):
        """
        Deletes an item.
        """
        item = session.get(self.model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        session.delete(item)
        session.commit()

        # HTMX will expect an empty response to remove the element
        return {}

    async def update_view(self, request: Request, item_id: int, session: Session = Depends(self.get_session)):
        """
        Renders the update view and handles form submission for updating an item.
        """
        item = session.get(self.model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if request.method == "POST":
            form_data = await request.form()
            for key, value in form_data.items():
                setattr(item, key, value)
            session.add(item)
            session.commit()
            session.refresh(item)
            # For now, let's redirect to the list view. HTMX will be added later.
            return {"message": "Item updated successfully"}

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item": item,
            "fields": list(self.model.model_fields.keys()),
        }
        return templates.TemplateResponse("update.html", context)

    async def create_view(self, request: Request, session: Session = Depends(self.get_session)):
        """
        Renders the create view and handles form submission for creating a new item.
        """
        if request.method == "POST":
            form_data = await request.form()
            item = self.model(**form_data)
            session.add(item)
            session.commit()
            session.refresh(item)
            # For now, let's redirect to the list view. HTMX will be added later.
            return {"message": "Item created successfully"} # This will be improved later

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
        }
        return templates.TemplateResponse("create.html", context)

    async def list_view(self, request: Request, session: Session = Depends(self.get_session)):
        """
        Renders the list view for the model.
        """
        items = session.query(self.model).all()
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
            "items": items,
        }
        return templates.TemplateResponse("list.html", context)

    async def detail_view(self, request: Request, item_id: int, session: Session = Depends(self.get_session)):
        """
        Renders the detail view for a single item.
        Assumes the model has an 'id' field.
        """
        item = session.get(self.model, item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        context = {
            "request": request,
            "item_name": f"{self.model.__name__} #{getattr(item, 'id', 'N/A')}",
            "item": item.model_dump(),
        }
        return templates.TemplateResponse("detail.html", context)

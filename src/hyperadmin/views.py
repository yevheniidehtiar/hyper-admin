import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# The templates are now in src/hyperadmin/templates
template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)


class ModelView:
    """
    A view class for a Pydantic model. This is a base class that should be subclassed.
    The subclass should define the `model` and `data` attributes.
    """

    model: type[BaseModel]
    data: list[BaseModel] = []

    def __init__(self):
        if not hasattr(self, "model"):
            raise ValueError("ModelView subclass must define a 'model' attribute.")

        self.router = APIRouter()
        self.add_routes()

    def add_routes(self):
        """
        Adds the list and detail view routes to the router.
        """
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}",
            self.list_view,
            methods=["GET"],
            name=f"{self.model.__name__.lower()}-list",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/{{item_id}}",
            self.detail_view,
            methods=["GET"],
            name=f"{self.model.__name__.lower()}-detail",
        )

    async def list_view(self, request: Request):
        """
        Renders the list view for the model.
        """
        context = {
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
            "items": [item.model_dump() for item in self.data],
        }
        return templates.TemplateResponse(name="list.html", context=context, request=request)

    async def detail_view(self, request: Request, item_id: int):
        """
        Renders the detail view for a single item.
        Assumes the model has an 'id' field.
        """
        # This is a simple linear search. Not efficient, but fine for the walking skeleton.
        item = next((item for item in self.data if getattr(item, "id", None) == item_id), None)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        context = {"item_name": f"{self.model.__name__} #{item.id}", "item": item.model_dump()}
        return templates.TemplateResponse(name="detail.html", context=context, request=request)

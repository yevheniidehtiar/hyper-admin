import os

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

from hyperadmin.core.adapters import BaseAdapter

template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=template_dir)


from starlette.responses import RedirectResponse


class DynamicModelView:
    def __init__(self, adapter: BaseAdapter):
        self.adapter = adapter
        self.model = adapter.model

    async def list_view(self, request: Request):
        """Renders the list view for the model."""
        items, _ = await self.adapter.list()
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
            "items": items,
        }
        return templates.TemplateResponse("list.html", context)

    async def detail_view(self, request: Request, item_id: int):
        """
        Renders the detail view for a single item.
        Assumes the model has an 'id' field.
        """
        item = await self.adapter.get(pk=item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        context = {
            "request": request,
            "item_name": f"{self.model.__name__} #{getattr(item, 'id', 'N/A')}",
            "item": item.model_dump(),
        }
        return templates.TemplateResponse("detail.html", context)

    async def create_form_view(self, request: Request):
        """Renders the create form."""
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
        }
        return templates.TemplateResponse("create.html", context)

    async def create_view(self, request: Request):
        """Handles form submission for creating a new item."""
        form_data = await request.form()
        await self.adapter.create(data=dict(form_data))
        return RedirectResponse(url=f"/admin/{self.model.__name__.lower()}", status_code=303)

    async def update_form_view(self, request: Request, item_id: int):
        """Renders the update form."""
        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item": item,
            "fields": list(self.model.model_fields.keys()),
        }
        return templates.TemplateResponse("update.html", context)

    async def update_view(self, request: Request, item_id: int):
        """Handles form submission for updating an item."""
        form_data = await request.form()
        await self.adapter.update(pk=item_id, data=dict(form_data))
        return RedirectResponse(url=f"/admin/{self.model.__name__.lower()}", status_code=303)

    async def delete_action(self, request: Request, item_id: int):
        """Deletes an item."""
        item = await self.adapter.get(pk=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        await self.adapter.delete(pk=item_id)

        return RedirectResponse(url=f"/admin/{self.model.__name__.lower()}", status_code=303)

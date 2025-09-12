import os
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.discover import app_label_var


class ModelView:
    def __init__(self, model):
        self.model = model

    def __init_subclass__(cls, **kwargs):
        model = kwargs.pop("model", None)
        super().__init_subclass__(**kwargs)
        if model:
            cls.model = model
            app_label = app_label_var.get()
            site.register(model, admin_class=cls, app_label=app_label)


class DynamicModelView:
    def __init__(
        self,
        adapter: BaseAdapter,
        options: AdminOptions,
        templates: Jinja2Templates,
        app_label: str | None,
    ):
        self.adapter = adapter
        self.model = adapter.model
        self.options = options
        self.templates = templates
        self.app_label = app_label

    def _get_template_name(self, view_name: str) -> str:
        model_name = self.model.__name__.lower()

        potential_templates = []
        if self.app_label:
            potential_templates.extend([
                f"{self.app_label}/{model_name}/{view_name}.html",
                f"{self.app_label}/{model_name}/default.html",
                f"{self.app_label}/{view_name}.html",
                f"{self.app_label}/default.html",
            ])
        potential_templates.extend([
            f"{view_name}.html",
            "default.html",
        ])

        for template_path in potential_templates:
            for search_path in self.templates.env.loader.searchpath:
                full_path = os.path.join(search_path, template_path)
                if os.path.exists(full_path):
                    return template_path

        return f"{view_name}.html"

    async def list_view(self, request: Request):
        """Renders the list view for the model."""
        items, _ = await self.adapter.list()
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
            "items": items,
        }
        template_name = self._get_template_name("list")
        return self.templates.TemplateResponse(template_name, context)

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
        template_name = self._get_template_name("detail")
        return self.templates.TemplateResponse(template_name, context)

    async def create_form_view(self, request: Request):
        """Renders the create form."""
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
        }
        template_name = self._get_template_name("create")
        return self.templates.TemplateResponse(template_name, context)

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
        template_name = self._get_template_name("update")
        return self.templates.TemplateResponse(template_name, context)

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

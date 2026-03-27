from fastapi import Request

from examples.simple.models import City, Country, Product, User
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class UserAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_filter = ["is_active", "user_type"]

    @action(label="Deactivate")
    async def deactivate(self, request: Request, item_id: int) -> None:
        """Set is_active=False for the given user."""
        user = await self.adapter.get(pk=item_id)
        if user:
            await self.adapter.update(pk=item_id, data={**user.model_dump(), "is_active": False})


class ProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class CountryAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class CityAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


site.register(User, UserAdmin)
site.register(Product, ProductAdmin)
site.register(Country, CountryAdmin)
site.register(City, CityAdmin)

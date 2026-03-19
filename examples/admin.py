from examples.models import Product, User
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class UserAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class ProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


site.register(User, UserAdmin)
site.register(Product, ProductAdmin)

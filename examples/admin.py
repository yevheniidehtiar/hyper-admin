from examples.models import User
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class UserAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


site.register(User, UserAdmin)

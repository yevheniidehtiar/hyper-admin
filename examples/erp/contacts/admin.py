from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site

from .models import Contact


class ContactAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["id", "name", "email", "contact_type"]
    list_filter = ["contact_type"]
    search_fields = ["name", "email", "phone"]


site.register(Contact, ContactAdmin)

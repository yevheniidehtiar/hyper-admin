from __future__ import annotations

from typing import ClassVar

from examples.erp.contacts.models import Contact
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class ContactAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = ["id", "name", "email", "contact_type"]
    list_filter: ClassVar[list[str]] = ["contact_type"]
    search_fields: ClassVar[list[str]] = ["name", "email", "phone"]


site.register(Contact, ContactAdmin)

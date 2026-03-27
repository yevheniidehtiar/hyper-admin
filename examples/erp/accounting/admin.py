from __future__ import annotations

from typing import ClassVar

from examples.erp.accounting.models import Account, JournalEntry, JournalLine
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class AccountAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = ["code", "name", "account_type"]
    list_filter: ClassVar[list[str]] = ["account_type"]
    search_fields: ClassVar[list[str]] = ["code", "name"]


class JournalEntryAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = ["id", "date_posted", "description"]


class JournalLineAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display: ClassVar[list[str]] = ["entry", "account", "debit", "credit"]


site.register(Account, AccountAdmin)
site.register(JournalEntry, JournalEntryAdmin)
site.register(JournalLine, JournalLineAdmin)

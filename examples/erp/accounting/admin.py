from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site

from .models import Account, JournalEntry, JournalLine


class AccountAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["code", "name", "account_type"]
    list_filter = ["account_type"]
    search_fields = ["code", "name"]


class JournalEntryAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["id", "date_posted", "description"]


class JournalLineAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["entry", "account", "debit", "credit"]


site.register(Account, AccountAdmin)
site.register(JournalEntry, JournalEntryAdmin)
site.register(JournalLine, JournalLineAdmin)

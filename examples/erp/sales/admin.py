from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site

from .models import Invoice, InvoiceItem


class InvoiceAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["number", "customer", "date_issued", "date_due", "status", "total_amount"]
    list_filter = ["status"]
    search_fields = ["number"]


class InvoiceItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["invoice", "description", "quantity", "unit_price", "total_price"]


site.register(Invoice, InvoiceAdmin)
site.register(InvoiceItem, InvoiceItemAdmin)

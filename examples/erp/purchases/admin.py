from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site

from .models import Bill, BillItem


class BillAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["reference", "supplier", "date_received", "date_due", "status", "total_amount"]
    list_filter = ["status"]
    search_fields = ["reference"]


class BillItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_display = ["bill", "description", "quantity", "unit_price", "total_price"]


site.register(Bill, BillAdmin)
site.register(BillItem, BillItemAdmin)

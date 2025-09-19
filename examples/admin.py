from examples.models import User
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class UserAdmin(ModelAdmin):
    pass


site.register(User, UserAdmin)

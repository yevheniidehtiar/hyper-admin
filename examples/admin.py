from examples.models import User
from hyperadmin.core.registry import site
from hyperadmin.views import ModelView


class UserAdmin(ModelView):
    model = User


site.register(User, UserAdmin)

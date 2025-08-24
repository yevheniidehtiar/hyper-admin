from hyperadmin.core.registry import site
from hyperadmin.views import ModelView

from examples.models import User


class UserAdmin(ModelView):
    model = User


site.register(User, UserAdmin)

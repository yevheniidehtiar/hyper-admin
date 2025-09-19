from pydantic import BaseModel


class AdminOptions(BaseModel):
    """Configuration options for a model in the admin interface."""

    can_create: bool = True
    can_edit: bool = True
    can_delete: bool = True
    can_list: bool = True
    can_detail: bool = True

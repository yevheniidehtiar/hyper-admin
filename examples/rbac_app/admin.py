from typing import ClassVar

from examples.rbac_app.models import Group, Permission, User, UserGroup, UserPermissions
from hyperadmin.views import ModelView


# Model Views for Admin Interface
class UserAdmin(ModelView, model=User):
    """Admin interface for User model."""

    list: ClassVar = [
        User.id,
        User.username,
        User.email,
        User.full_name,
        User.is_active,
        User.created_at,
    ]
    column_searchable_list: ClassVar = [
        User.username,
        User.email,
        User.first_name,
        User.last_name,
    ]
    column_sortable_list: ClassVar = [User.id, User.username, User.email, User.created_at]
    column_filters: ClassVar = [User.is_active, User.is_superuser, User.created_at]

    form_columns: ClassVar = [
        User.username,
        User.email,
        User.first_name,
        User.last_name,
        User.is_active,
        User.is_superuser,
    ]

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


class GroupAdmin(ModelView, model=Group):
    """Admin interface for Group model."""

    column_list: ClassVar = [
        Group.id,
        Group.name,
        Group.description,
        Group.is_active,
        Group.created_at,
    ]
    column_details_list: ClassVar = [
        Group.id,
        Group.name,
        Group.description,
        Group.is_active,
        Group.created_at,
    ]
    column_searchable_list: ClassVar = [Group.name, Group.description]
    column_sortable_list: ClassVar = [Group.id, Group.name, Group.created_at]
    column_filters: ClassVar = [Group.is_active, Group.created_at]

    form_columns: ClassVar = [Group.name, Group.description, Group.is_active]

    name = "Group"
    name_plural = "Groups"
    icon = "fa-solid fa-users"


class UserGroupAdmin(ModelView, model=UserGroup):
    """Admin interface for UserGroup model."""

    column_list: ClassVar = [
        UserGroup.user,
        UserGroup.group,
        UserGroup.joined_at,
        UserGroup.is_active,
    ]
    column_details_list: ClassVar = [
        UserGroup.id,
        UserGroup.user,
        UserGroup.group,
        UserGroup.joined_at,
        UserGroup.is_active,
    ]
    column_sortable_list: ClassVar = [UserGroup.id, UserGroup.joined_at]
    column_filters: ClassVar = [UserGroup.is_active, UserGroup.joined_at]

    form_columns: ClassVar = [
        UserGroup.user,
        UserGroup.group,
        UserGroup.joined_at,
        UserGroup.is_active,
    ]

    name = "User Group"
    name_plural = "User Groups"
    icon = "fa-solid fa-link"


class PermissionAdmin(ModelView, model=Permission):
    """Admin interface for Permission model."""

    column_list: ClassVar = [
        Permission.id,
        Permission.name,
        Permission.codename,
        Permission.content_type,
        Permission.created_at,
    ]
    column_details_list: ClassVar = [
        Permission.id,
        Permission.name,
        Permission.codename,
        Permission.description,
        Permission.content_type,
        Permission.created_at,
    ]
    column_searchable_list: ClassVar = [
        Permission.name,
        Permission.codename,
        Permission.description,
    ]
    column_sortable_list: ClassVar = [
        Permission.id,
        Permission.name,
        Permission.codename,
        Permission.created_at,
    ]
    column_filters: ClassVar = [Permission.content_type, Permission.created_at]

    form_columns: ClassVar = [
        Permission.name,
        Permission.codename,
        Permission.description,
        Permission.content_type,
    ]

    name = "Permission"
    name_plural = "Permissions"
    icon = "fa-solid fa-key"


class UserPermissionsAdmin(ModelView, model=UserPermissions):
    """Admin interface for UserPermissions model."""

    column_list: ClassVar = [
        UserPermissions.id,
        UserPermissions.user,
        UserPermissions.permission,
        UserPermissions.granted_at,
        UserPermissions.is_active,
    ]
    column_details_list: ClassVar = [
        UserPermissions.id,
        UserPermissions.user,
        UserPermissions.permission,
        UserPermissions.granted_at,
        UserPermissions.granted_by,
        UserPermissions.is_active,
    ]
    column_sortable_list: ClassVar = [UserPermissions.id, UserPermissions.granted_at]
    column_filters: ClassVar = [UserPermissions.is_active, UserPermissions.granted_at]

    form_columns: ClassVar = [
        UserPermissions.user,
        UserPermissions.permission,
        UserPermissions.granted_by,
        UserPermissions.is_active,
    ]

    name = "User Permission"
    name_plural = "User Permissions"
    icon = "fa-solid fa-shield-alt"

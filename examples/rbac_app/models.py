from datetime import datetime

from fastapi_storages import FileSystemStorage, StorageFile
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel

avatar_storage = FileSystemStorage("./uploads/avatars")
personal_key_storage = FileSystemStorage("./uploads/user_pk")


class User(SQLModel, table=True):
    """User model with authentication and profile information."""

    __tablename__ = "users"

    model_config = {
        "arbitrary_types_allowed": True,
    }
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, max_length=50, unique=True)
    email: str = Field(index=True, max_length=100, unique=True)
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)

    # File upload fields
    avatar: StorageFile | None = Field(
        default=None,
        sa_column=Column(ImageType(avatar_storage)),
    )
    personal_key: StorageFile | None = Field(
        default=None,
        sa_column=Column(FileType(personal_key_storage)),
    )

    # Relationships
    user_groups: list["UserGroup"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "foreign_keys": "UserGroup.user_id",
            "lazy": "selectin",
        },
    )
    user_permissions: list["UserPermissions"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "foreign_keys": "UserPermissions.user_id",
            "lazy": "selectin",
        },
    )

    @property
    def full_name(self) -> str:
        """Return user's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def groups(self) -> list["Group"]:
        """Get all groups this user belongs to."""
        return [ug.group for ug in self.user_groups if ug.group]

    @property
    def permissions(self) -> list["Permission"]:
        """Get all permissions this user has."""
        return [up.permission for up in self.user_permissions if up.permission]

    def __str__(self):
        return self.full_name


class Group(SQLModel, table=True):
    """Group model for organizing users."""

    __tablename__ = "groups"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=80, unique=True)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    user_groups: list["UserGroup"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={
            "foreign_keys": "UserGroup.group_id",
            "lazy": "selectin",
        },
    )

    def __str__(self) -> str:
        return self.name

    @property
    def users(self) -> list["User"]:
        """Get all users in this group."""
        return [ug.user for ug in self.user_groups if ug.user]


class UserGroup(SQLModel, table=True):
    """Many-to-many relationship between User and Group."""

    __tablename__ = "user_groups"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    group_id: int = Field(foreign_key="groups.id", index=True)
    joined_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = Field(default=True)
    # Relationships
    user: User | None = Relationship(
        back_populates="user_groups",
        sa_relationship_kwargs={"foreign_keys": "UserGroup.user_id"},
    )
    group: Group | None = Relationship(
        back_populates="user_groups",
        sa_relationship_kwargs={"foreign_keys": "UserGroup.group_id"},
    )

    def __str__(self) -> str:
        return f"{self.user.name} - {self.group.name}" if self.user and self.group else ""


class Permission(SQLModel, table=True):
    """Permission model for defining what actions users can perform."""

    __tablename__ = "permissions"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=100, unique=True)
    codename: str = Field(index=True, max_length=100, unique=True)
    description: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=100)  # e.g., 'user', 'group', etc.
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    user_permissions: list["UserPermissions"] = Relationship(
        back_populates="permission",
        sa_relationship_kwargs={
            "foreign_keys": "UserPermissions.permission_id",
            "lazy": "selectin",
        },
    )

    def __str__(self) -> str:
        return self.name

    @property
    def users(self) -> list["User"]:
        """Get all users who have this permission."""
        return [up.user for up in self.user_permissions if up.user]


class UserPermissions(SQLModel, table=True):
    """Many-to-many relationship between User and Permission."""

    __tablename__ = "user_permissions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    permission_id: int = Field(foreign_key="permissions.id", index=True)
    granted_at: datetime = Field(default_factory=datetime.now)
    granted_by: int | None = Field(default=None, foreign_key="users.id")
    is_active: bool = Field(default=True)

    # Relationships
    user: User | None = Relationship(
        back_populates="user_permissions",
        sa_relationship_kwargs={"foreign_keys": "UserPermissions.user_id"},
    )
    permission: Permission | None = Relationship(
        back_populates="user_permissions",
        sa_relationship_kwargs={"foreign_keys": "UserPermissions.permission_id"},
    )

    def __str__(self) -> str:
        return (
            f"{self.user.full_name} - {self.permission.name}"
            if self.user and self.permission
            else ""
        )

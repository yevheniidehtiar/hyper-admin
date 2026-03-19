from datetime import datetime

from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    """User model with authentication and profile information."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, max_length=50, unique=True)
    email: str = Field(index=True, max_length=100, unique=True)
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)

    # Relationships
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

    def __str__(self):
        return self.username

    def has_perm(self, codename: str) -> bool:
        """Check if the user has a specific permission."""
        if self.is_superuser:
            return True
        if not self.is_active:
            return False
        return any(
            up.permission.codename == codename for up in self.user_permissions if up.permission
        )


class Permission(SQLModel, table=True):
    """Permission model for defining what actions users can perform."""

    __tablename__ = "permissions"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=100, unique=True)
    codename: str = Field(index=True, max_length=100, unique=True)
    description: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=100)
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


class UserPermissions(SQLModel, table=True):
    """Many-to-many relationship between User and Permission."""

    __tablename__ = "user_permissions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    permission_id: int = Field(foreign_key="permissions.id", index=True)
    granted_at: datetime = Field(default_factory=datetime.now)
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
            f"{self.user.username} - {self.permission.name}"
            if self.user and self.permission
            else ""
        )
